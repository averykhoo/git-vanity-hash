import os
import subprocess
import time
from hashlib import sha1


def check_output(*args, env=None):
    if env is None:
        return subprocess.check_output(args).decode('ascii').rstrip('\n')
    else:
        return subprocess.check_output(args, env=env).decode('ascii').rstrip('\n')


def brute_force(raw_payload, desired_prefix, start_idx=0, end_idx=0xf_FFFF_FFFF):
    """
    Generate SHA1 hash of the commit object.
    """
    assert start_idx >= 0
    assert end_idx <= 0x10_0000_0000
    assert int(desired_prefix, 16) <= 0xFFFF_FFFF

    t = time.perf_counter()

    expected_length = len(raw_payload) + 12  # 10 hex digits and 2 newlines
    h0 = sha1()
    h0.update(f'commit {expected_length}\0{raw_payload}\n'.encode('latin-1'))

    def _brute_force(hash_obj, num_chars):
        for char in (b'0', b'1', b'2', b'3', b'4', b'5', b'6', b'7', b'8', b'9', b'a', b'b', b'c', b'd', b'e', b'f'):
            _hash_obj = hash_obj.copy()
            _hash_obj.update(char)
            if num_chars == 1:
                _hash_obj.update(b'\n')
                if _hash_obj.hexdigest().startswith(desired_prefix):
                    return _hash_obj.hexdigest(), char
            else:
                assert num_chars > 1
                solution, magic = _brute_force(_hash_obj, num_chars - 1)
                if solution:
                    return solution, char + magic
        return None, None

    solution, magic_string = _brute_force(h0, 10)

    t = time.perf_counter() - t
    print(t, 'secs')
    return solution, magic_string.decode('ascii')


def make_commit(commit, prefix):
    """
    Make a commit with the prefix.
    """
    payload = check_output('git', 'cat-file', 'commit', commit)
    message = check_output('git', 'rev-list', '--max-count=1', '--format=%B', commit).split('\n', 1)[1]
    assert payload.endswith(message)

    expected, string = brute_force(payload, prefix)
    assert expected is not None

    format_names = {'GIT_AUTHOR_NAME':     'an',
                    'GIT_AUTHOR_EMAIL':    'ae',
                    'GIT_AUTHOR_DATE':     'ad',
                    'GIT_COMMITTER_NAME':  'cn',
                    'GIT_COMMITTER_EMAIL': 'ce',
                    'GIT_COMMITTER_DATE':  'cd',
                    }

    env = os.environ.copy()
    for name, fmt in format_names.items():
        env[name] = check_output('git', '--no-pager', 'show', '-s', f'--format=%{fmt}')
        print(name, env[name])

    print(check_output('git', 'commit', '--amend', '-m', f'{message}\n{string}\n', env=env))

    # check that the full sha1 hash of the commit is what we expect
    assert expected == check_output('git', 'rev-parse', commit)


if __name__ == '__main__':
    make_commit('HEAD', 'beef')
