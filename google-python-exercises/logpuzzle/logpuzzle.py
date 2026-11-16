import os
import re
import sys
import urllib.request


def read_urls(filename):
    host = filename[filename.index('_') + 1:]
    url_dict = {}
    with open(filename, encoding='utf-8') as f:
        for line in f:
            m = re.search(r'"GET (\S+)', line)
            if m and 'puzzle' in m.group(1):
                url_dict['http://' + host + m.group(1)] = 1
    return sorted(url_dict.keys())


def download_images(img_urls, dest_dir):
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)

    index = open(os.path.join(dest_dir, 'index.html'), 'w', encoding='utf-8')
    index.write('<html><body>\n')

    for i, url in enumerate(img_urls):
        local = 'img%d.jpg' % i
        print('Retrieving... ' + url)
        urllib.request.urlretrieve(url, os.path.join(dest_dir, local))
        index.write('<img src="%s">' % local)

    index.write('\n</body></html>\n')
    index.close()


def main():
    args = sys.argv[1:]
    if not args:
        print('usage: [--todir dir] logfile')
        sys.exit(1)

    todir = ''
    if args[0] == '--todir':
        todir = args[1]
        del args[0:2]

    img_urls = read_urls(args[0])

    if todir:
        download_images(img_urls, todir)
    else:
        print('\n'.join(img_urls))


if __name__ == '__main__':
    main()
