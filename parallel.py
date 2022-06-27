import multiprocessing as mp
import os

from main import brute_force
from main import check_output


def worker(idx, payload, prefix):
    print(f'worker {idx=} started')
    try:
        return brute_force(payload, prefix, f'{idx:02x}', len(prefix) - 1)
    except RuntimeError:
        return None


def make_commit_parallel(commit, prefix):
    # note that this strips multiple trailing newlines from the existing message
    payload = check_output('git', 'cat-file', 'commit', commit)
    message = check_output('git', 'rev-list', '--max-count=1', '--format=%B', commit).split('\n', 1)[1]
    assert payload.endswith(message)

    def quit_callback(arg):
        if arg is None:
            return

        # stop pool
        p.terminate()

        # print
        expected, magic_string = arg
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
        print(check_output('git', 'commit', '--amend', '-m', f'{message}\n{magic_string}\n', env=env))

        # check that the full sha1 hash of the commit is what we expect
        assert expected == check_output('git', 'rev-parse', commit)

    for i in range(0x100):
        p.apply_async(worker, args=(i, payload, prefix), callback=quit_callback)

    p.close()
    p.join()


if __name__ == '__main__':
    p = mp.Pool(mp.cpu_count())
    make_commit_parallel('HEAD', '000000')
