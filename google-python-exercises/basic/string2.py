def verbing(s):
    if len(s) < 3:
        return s
    if s.endswith('ing'):
        return s + 'ly'
    return s + 'ing'


def not_bad(s):
    not_i = s.find('not')
    bad_i = s.find('bad')
    if not_i != -1 and bad_i != -1 and bad_i > not_i:
        return s[:not_i] + 'good' + s[bad_i + 3:]
    return s


def front_back(a, b):
    a_mid = (len(a) + 1) // 2
    b_mid = (len(b) + 1) // 2
    return a[:a_mid] + b[:b_mid] + a[a_mid:] + b[b_mid:]


def test(got, expected):
    print((' OK ' if got == expected else '  X ') + 'got: %r expected: %r' % (got, expected))


def main():
    print('verbing')
    test(verbing('hail'), 'hailing')
    test(verbing('swiming'), 'swimingly')
    test(verbing('do'), 'do')
    print()
    print('not_bad')
    test(not_bad('This movie is not so bad'), 'This movie is good')
    test(not_bad('This dinner is not that bad!'), 'This dinner is good!')
    test(not_bad('This tea is not hot'), 'This tea is not hot')
    test(not_bad("It's bad yet not"), "It's bad yet not")
    print()
    print('front_back')
    test(front_back('abcd', 'xy'), 'abxcdy')
    test(front_back('abcde', 'xyz'), 'abcxydez')
    test(front_back('Kitten', 'Donut'), 'KitDontenut')


if __name__ == '__main__':
    main()
