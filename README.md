# Git Vanity Hashes

customize the first few chars of your git hash

## TODO:

* [x] use hash clone to avoid re-hashing
* [x] multiprocessing pooling
  * https://stackoverflow.com/questions/36962462/terminate-a-python-multiprocessing-program-once-a-one-of-its-workers-meets-a-cer/36962624#36962624
* [ ] cython
* [x] unroll the recursion into a loop  <-- turns out this is slower, probably due to all the getting and setting

## See also:

* https://github.com/clickyotomy/vanity-commit
* https://github.com/tochev/git-vanity
* https://github.com/vog/beautify_git_hash
