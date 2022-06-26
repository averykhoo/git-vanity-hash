import os
import string
import subprocess
import time
from hashlib import sha1


def check_output(*args, env=None):
    return subprocess.check_output(args, env=env).decode('ascii').rstrip('\n')


def brute_force(raw_payload, desired_prefix, random_word_length=None):
    """
    Generate SHA1 hash of the commit object.
    """
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
    alphabet_len = len(alphabet)

    # we don't need an arbitrarily deep stack because we know exactly how many chars we want in the word
    current_chars = [0] * random_word_length
    hash_objs = [hash_obj]
    for _ in range(random_word_length):
        hash_obj_copy = hash_objs[-1].copy()
        hash_obj_copy.update(alphabet[0])
        hash_objs.append(hash_obj_copy)

    # brute force loop
    solution = None
    t_start = time.perf_counter()
    while True:

        # test current config
        _hash_obj = hash_objs[-1].copy()
        _hash_obj.update(b'\n')
        _prefix = _hash_obj.hexdigest()[:prefix_len]
        if _prefix == desired_prefix:
            solution = _hash_obj.hexdigest()
            break

        # increment the alphabet indices
        idx = random_word_length
        while idx:
            idx -= 1
            current_chars[idx] = (current_chars[idx] + 1) % alphabet_len
            if current_chars[idx]:
                break

        # looped right back around to zero, meaning we failed to find a matching hash
        else:
            assert all(c == 0 for c in current_chars)
            break

        # update the hash objects
        while idx < random_word_length:
            _hash_obj = hash_objs[idx].copy()
            _hash_obj.update(alphabet[current_chars[idx]])
            idx += 1
            hash_objs[idx] = _hash_obj

    # found a solution, hopefully
    t_end = time.perf_counter()
    magic_string = b''.join(alphabet[c] for c in current_chars)

    # handle overflow so that we can still get stats
    if all(char == alphabet[0][0] for char in magic_string):
        magic_string = alphabet[1] + magic_string

    # stats
    t = t_end - t_start
    print(round(t, 2), 'secs')
    print(round(int(magic_string, 36) / t, 2), 'hashes per second')

    # for i, h in enumerate(hash_objs):
    #     print(i, h.hexdigest())

    # h0 = hash_objs[0].copy()
    # for i, c in enumerate(current_chars):
    #     h0.update(alphabet[c])
    #     print(i, h0.hexdigest())
    # h0.update(b'\n')
    # print(h0.hexdigest())

    # return string as ascii so we can append it to the comment
    if solution:
        return solution, magic_string.decode('ascii')
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
    make_commit('HEAD', '00000')
