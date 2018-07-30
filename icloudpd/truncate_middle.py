def truncate_middle(str, length):
    if len(str) <= length:
        return str
    if length < 0:
        raise ValueError("n must be greater than or equal to 1")
    if length <= 3:
        return '...'[0:length]
    end_length = int(length) // 2 - 2
    start_length = length - end_length - 4
    if end_length < 1:
        end_length = 1
    return '{0}...{1}'.format(str[:start_length], str[-end_length:])
