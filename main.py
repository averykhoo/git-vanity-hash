import os
import string
import subprocess
import time
from hashlib import sha1
from typing import Optional
from typing import TYPE_CHECKING
from typing import Tuple
from typing import Union

# PyCharm will read this first type definition as the default
if not TYPE_CHECKING:
    Sha1Type = type(sha1())

# mypy will be tricked into believing this is the type (but it's never actually created at runtime)
else:
    class Sha1Type:
        def copy(self) -> 'Sha1Type':
            return self

        def update(self, _bytes: bytes):
            pass

        def hexdigest(self) -> str:
            return self.__class__.__name__


def check_output(*args, env=None):
    return subprocess.check_output(args, env=env).decode('ascii').rstrip('\n')


def brute_force(raw_payload: str,
                desired_prefix: str,
                nonce_prefix: str = '',
                nonce_length: Optional[int] = None,
                ) -> Tuple[str, str]:
    """
    brute-force the nonce we need to append to the commit message in order to get the desired git hash prefix
    if not found, raises a RuntimeError

    :param raw_payload:    output of `git cat-file commit HEAD`
    :param desired_prefix: hash prefix, usually 7 chars long; e.g. '0000000'
    :param nonce_prefix:   optional prefix to identify the nonce in the commit message, e.g. '\nnonce-'
    :param nonce_length:   length of nonce; if not specified, defaults to length of desired prefix plus two
    :return:               tuple of (expected_hash: str, nonce: str)
    """
    assert isinstance(desired_prefix, str) and len(desired_prefix) > 0
    assert int(desired_prefix, 16) <= 0xFFFF_FFFF
    if nonce_length is None:
        nonce_length = len(desired_prefix) + 2  # we can only be so unlucky
    assert isinstance(nonce_length, int) and nonce_length > 0

    # initialize hash object with the prefix
    expected_length = len(raw_payload) + 1 + len(nonce_prefix) + nonce_length + 1  # each +1 is a '\n'
    hash_obj = sha1(f'commit {expected_length}\0{raw_payload}\n{nonce_prefix}'.encode('ascii'))
    desired_prefix_len = len(desired_prefix)

    # we can use up to 96, but python's `int()` can only parse up to 36, and it's nice to have the hashes rate
    alphabet = tuple(map(str.encode, string.printable[:36]))

    def _brute_force(parent_hash_obj: Sha1Type,
                     num_chars: int,
                     ) -> Union[Tuple[bool, None], Tuple[str, bytes]]:
        """
        this is the (recursive) hot loop
        it clones the hash objects in order to avoid re-hashing the same data
        other optimizations are noted in the comments,
            although some are just measurement-based and are not rooted in theory
        this function is more easily written recursively,
            and unrolling it into an iterative loop has (so far) proven to be slower
        """
        for char in alphabet:
            current_hash_obj = parent_hash_obj.copy()
            current_hash_obj.update(char)

            # recurse for the specified number of chars
            if num_chars > 0:  # somehow `x > 0` runs faster than `x != 0`
                sha1_hash, partial_nonce = _brute_force(current_hash_obj, num_chars - 1)
                if sha1_hash:  # somehow False seems to be faster than None
                    # found the magic string and exiting, this code does not need to be optimized
                    assert isinstance(sha1_hash, str)  # convince mypy
                    assert isinstance(partial_nonce, bytes)  # convince mypy
                    return sha1_hash, char + partial_nonce

            # for the final recursion, add the nonce suffix and test whether we got the desired hash prefix
            else:
                current_hash_obj.update(b'\n')  # inlining the byte is faster
                _prefix = current_hash_obj.hexdigest()[:desired_prefix_len]
                if _prefix == desired_prefix:  # comparing interned strings is faster
                    return current_hash_obj.hexdigest(), char

        # hash prefix not found
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
        assert isinstance(expected_hash, str)  # convince mypy
        return expected_hash, magic_string.decode('ascii')
    else:
        raise RuntimeError(f'no nonce found to get {desired_prefix=}')


def make_commit(commit, prefix):
    # note that this strips multiple trailing newlines from the existing message
    payload = check_output('git', 'cat-file', 'commit', commit)
    message = check_output('git', 'rev-list', '--max-count=1', '--format=%B', commit).split('\n', 1)[1]
    assert payload.endswith(message)

    # brute force what we need to append in order to get the desired hash prefix
    expected, magic_string = brute_force(payload, prefix)
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
