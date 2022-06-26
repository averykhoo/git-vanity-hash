import os
import string
import subprocess
import time
from hashlib import sha1


def check_output(*args, env=None):
    return subprocess.check_output(args, env=env).decode('ascii').rstrip('\n')


def brute_force(raw_payload, desired_prefix, random_word_length=None):
    assert isinstance(desired_prefix, str) and len(desired_prefix) > 0
    assert int(desired_prefix, 16) <= 0xFFFF_FFFF
    if random_word_length is None:
        random_word_length = len(desired_prefix) + 2  # we can only be so unlucky
    assert isinstance(random_word_length, int) and random_word_length > 0

    # initialize hash object with the prefix
    expected_length = len(raw_payload) + random_word_length + 2
    hash_obj = sha1(f'commit {expected_length}\0{raw_payload}\n'.encode('latin-1'))
    prefix_len = len(desired_prefix)

    # we can use up to 96, but python's `int()` can only parse up to 36, and it's nice to have the hashes rate
    alphabet = tuple(map(str.encode, string.printable[:36]))

    def _brute_force(hash_obj, num_chars):
        for char in alphabet:
            _hash_obj = hash_obj.copy()
            _hash_obj.update(char)
            if num_chars:
                solution, magic = _brute_force(_hash_obj, num_chars - 1)
                if solution:
                    return solution, char + magic
            else:
                _hash_obj.update(b'\n')
                _prefix = _hash_obj.hexdigest()[:prefix_len]
                if _prefix == desired_prefix:
                    return _hash_obj.hexdigest(), char
        return None, None

    # mine bitcoin
    t_start = time.perf_counter()
    solution, magic_string = _brute_force(hash_obj, random_word_length - 1)
    t_end = time.perf_counter()

    # handle overflow by clamping to max value so that we can still get stats
    if magic_string is None:
        magic_string = b''.join([alphabet[-1]] * random_word_length)

    # stats
    t = t_end - t_start
    print(round(t, 2), 'secs')
    print(round(int(magic_string, len(alphabet)) / t, 2), 'hashes per second')

    # return string as ascii so we can append it to the comment
    return solution, magic_string.decode('ascii')


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
