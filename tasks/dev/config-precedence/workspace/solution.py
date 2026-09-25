def resolve_port(cli, env, config):
    value = cli or env.get('PORT') or config.get('port') or 8000
    return int(value)
