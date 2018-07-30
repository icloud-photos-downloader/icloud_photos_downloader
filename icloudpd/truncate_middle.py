def truncate_middle(s, n):
    if len(s) <= n:
        return s
    if n < 1:
        raise ValueError("n must be greater than or equal to 1")
    if n <= 3:
        return '...'[0:n]
    n_2 = int(n) // 2 - 2
    n_1 = n - n_2 - 4
    if n_2 < 1:
        n_2 = 1
    return '{0}...{1}'.format(s[:n_1], s[-n_2:])
