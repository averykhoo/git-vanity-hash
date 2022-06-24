import os
import subprocess
import time
from hashlib import sha1


def who():
    """
    Get commit metadata about authors, committers.
    """
    format_names = {'author-name':     'an', 'author-email': 'ae', 'author-date': 'ad', 'committer-name': 'cn',
                    'committer-email': 'ce', 'committer-date': 'cd', }

    metadata = {
        name: subprocess.check_output(['git', '--no-pager', 'show', '-s', f'--format=%{fmt}']).decode('ascii').rstrip(
            '\n') for name, fmt in format_names.items()}

    print(metadata)
    return metadata


def get_full_sha1_hash(commit):
    """
    Get the full SHA1 of the commit (if refspecs are used).
    """
    return subprocess.check_output(['git', 'rev-parse', commit]).decode('ascii').rstrip('\n')


def brute_force(raw_payload, desired_prefix, start_idx=0, end_idx=0xf_FFFF_FFFF):
    """
    Generate SHA1 hash of the commit object.
    """
    assert start_idx >= 0
    assert end_idx <= 0x10_0000_0000
    assert int(desired_prefix, 16) <= 0xFFFF_FFFF

    expected_length = len(raw_payload) + 12  # 10 hex digits and 2 newlines
    h = sha1()
    h.update(f'commit {expected_length}\0{raw_payload}\n'.encode('latin-1'))

    for i in range(start_idx, end_idx):
        _h = h.copy()
        _h.update(f'{i:010x}\n'.encode('latin-1'))
        solution = _h.hexdigest()

        if _h.hexdigest().startswith(desired_prefix):
            return solution, f'{i:010x}\n'

    return None, None


def make_commit(commit, prefix):
    """
    Make a commit with the prefix.
    """

    # full commit content
    payload = subprocess.check_output(['git', 'cat-file', 'commit', commit]).decode('ascii').rstrip('\n')

    # git message
    message = \
    subprocess.check_output(['git', 'rev-list', '--max-count=1', '--format=%B', commit]).decode('ascii').rstrip(
        '\n').split('\n', 1)[1]

    expected, string = brute_force(payload, prefix)
    assert expected is not None

    metadata = who()

    env = os.environ.copy()
    env['GIT_AUTHOR_NAME'] = metadata['author-name']
    env['GIT_AUTHOR_EMAIL'] = metadata['author-email']
    env['GIT_AUTHOR_DATE'] = metadata['author-date']
    env['GIT_COMMITTER_NAME'] = metadata['committer-name']
    env['GIT_COMMITTER_EMAIL'] = metadata['committer-email']
    env['GIT_COMMITTER_DATE'] = metadata['committer-date']

    messages = ['-m'] + [message + '\n' + string + '\n']
    print(payload)

    subprocess.check_call(['git', 'commit', '--amend'] + messages, env=env)

    assert expected == get_full_sha1_hash(commit)


if __name__ == '__main__':
    start = time.time()
    make_commit('HEAD', '000000')
    end = time.time()
    print(end - start)
