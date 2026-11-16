import os
import re
import shutil
import subprocess
import sys


def get_special_paths(dirs):
    result = []
    for d in dirs:
        for fn in os.listdir(d):
            if re.search(r'__(\w+)__', fn):
                result.append(os.path.abspath(os.path.join(d, fn)))
    return result


def copy_to(paths, to_dir):
    if not os.path.exists(to_dir):
        os.mkdir(to_dir)
    for path in paths:
        shutil.copy(path, os.path.join(to_dir, os.path.basename(path)))


def zip_to(paths, zipfile):
    cmd = 'zip -j ' + zipfile + ' ' + ' '.join(paths)
    print("Command I'm going to do: " + cmd)
    subprocess.call(cmd, shell=True)


def main():
    args = sys.argv[1:]
    if not args:
        print('usage: [--todir dir][--tozip zipfile] dir [dir ...]')
        sys.exit(1)

    todir = ''
    if args[0] == '--todir':
        todir = args[1]
        del args[0:2]

    tozip = ''
    if args[0] == '--tozip':
        tozip = args[1]
        del args[0:2]

    if not args:
        print('error: must specify one or more dirs')
        sys.exit(1)

    paths = get_special_paths(args)
    if todir:
        copy_to(paths, todir)
    elif tozip:
        zip_to(paths, tozip)
    else:
        print('\n'.join(paths))


if __name__ == '__main__':
    main()
