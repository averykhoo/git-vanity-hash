import os
import string
import subprocess
import time
from hashlib import sha1
from typing import Optional
from typing import Tuple
from typing import Union

Sha1Type = type(sha1())


def check_output(*args, env=None):
    return subprocess.check_output(args, env=env).decode('ascii').rstrip('\n')


def brute_force(raw_payload: str,
                desired_prefix: str,
                nonce_prefix: str = '',
                nonce_length: Optional[int] = None,
                ) -> Union[Tuple[None, None], Tuple[str, str]]:
    """

    :param raw_payload:
    :param desired_prefix:
    :param nonce_prefix:
    :param nonce_length:
    :return:
    """
    assert isinstance(desired_prefix, str) and len(desired_prefix) > 0
    assert int(desired_prefix, 16) <= 0xFFFF_FFFF
    if nonce_length is None:
        nonce_length = len(desired_prefix) + 2  # we can only be so unlucky
    assert isinstance(nonce_length, int) and nonce_length > 0

    # initialize hash object with the prefix
    expected_length = len(raw_payload) + 1 + len(nonce_prefix) + nonce_length + 1
    hash_obj = sha1(f'commit {expected_length}\0{raw_payload}\n{nonce_prefix}'.encode('ascii'))
    desired_prefix_len = len(desired_prefix)

    # we can use up to 96, but python's `int()` can only parse up to 36, and it's nice to have the hashes rate
    alphabet = tuple(map(str.encode, string.printable[:36]))

    def _brute_force(parent_hash_obj: Sha1Type,
                     num_chars: int,
                     ) -> Union[Tuple[bool, None], Tuple[str, bytes]]:
        """
        this is the (recursive) hot loop
        """
        for char in alphabet:
            current_hash_obj = parent_hash_obj.copy()
            current_hash_obj.update(char)

            # recurse for the specified number of chars
            if num_chars > 0:  # somehow runs faster than `!= 0`
                sha1_hash, partial_nonce = _brute_force(current_hash_obj, num_chars - 1)
                if sha1_hash:  # False is faster than None
                    # found the magic string and exiting, this code does not need to be optimized
                    assert isinstance(sha1_hash, str)
                    assert isinstance(partial_nonce, bytes)
                    return sha1_hash, char + partial_nonce

            # for the final recursion, add the nonce suffix and test whether we got the desired hash prefix
            else:
                current_hash_obj.update(b'\n')
                _prefix = current_hash_obj.hexdigest()[:desired_prefix_len]
                if _prefix == desired_prefix:  # comparing interned strings is much faster
                    return current_hash_obj.hexdigest(), char
        return False, None

    # mine bitcoin
    t_start = time.perf_counter()
    expected_hash, magic_string = _brute_force(hash_obj, nonce_length - 1)
    t_end = time.perf_counter()

    # handle overflow by clamping to max value so that we can still get stats
    if magic_string is None:
        magic_string = b''.join([alphabet[-1]] * nonce_length)

    # stats
    t_elapsed = t_end - t_start
    print(round(t_elapsed, 2), 'secs')
    print(round(int(magic_string, len(alphabet)) / t_elapsed, 2), 'hashes per second')

    # return string as ascii so we can append it to the comment
    if expected_hash:
        return expected_hash, magic_string.decode('ascii')
    else:
        return None, None


def make_commit(commit, prefix):
    # note that this strips multiple trailing newlines from the existing message
    payload = check_output('git', 'cat-file', 'commit', commit)
    message = check_output('git', 'rev-list', '--max-count=1', '--format=%B', commit).split('\n', 1)[1]
    assert payload.endswith(message)

    # brute force what we need to append in order to get the desired hash prefix
    expected, magic_string = brute_force(payload, prefix)
    assert expected is not None
    print(f'found {magic_string=} that changes {commit=} to start with {prefix=}')

    # we need to set this to the same value in order to make the hash match
    format_names = {'GIT_AUTHOR_NAME':     'an',
                    'GIT_AUTHOR_EMAIL':    'ae',
                    'GIT_AUTHOR_DATE':     'ad',
                    'GIT_COMMITTER_NAME':  'cn',
                    'GIT_COMMITTER_EMAIL': 'ce',
                    'GIT_COMMITTER_DATE':  'cd',
                    }

    # use a copy of the current environment and set the keys above
    env = os.environ.copy()
    for name, fmt in format_names.items():
        env[name] = check_output('git', '--no-pager', 'show', '-s', f'--format=%{fmt}')

    # update the specified commit with the magic string
    print('git', 'commit', '--amend', '-m', f'{message}\n{magic_string}\n')
    print(env)
    print(check_output('git', 'commit', '--amend', '-m', f'{message}\n{magic_string}\n', env=env))

    # check that the full sha1 hash of the commit is what we expect
    assert expected == check_output('git', 'rev-parse', commit)


if __name__ == '__main__':
    make_commit('HEAD', 'abcdef')
