def resolve_port(cli, env, config):
    for value in (cli, env.get('PORT'), config.get('port'), 8000):
        if value is None or value == '':
            continue
        if type(value) is not int and not (isinstance(value, str) and value.isascii() and value.isdecimal()):
            raise ValueError('invalid port')
        port = int(value)
        if not 0 <= port <= 65535:
            raise ValueError('invalid port')
        return port
