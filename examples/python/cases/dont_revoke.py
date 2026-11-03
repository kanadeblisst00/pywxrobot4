"""防撤回：调用 /other/dontrevoke 打开或关闭。"""

import argparse


def run(client, config, args):
    del config
    parser = argparse.ArgumentParser(prog="dont_revoke", description="打开或关闭防撤回")
    parser.add_argument("--revoke", choices=("true", "false"), required=True)
    options = parser.parse_args(args)
    result = client.post("/other/dontrevoke", {"revoke": options.revoke == "true"}, write=True)
    print(result)
    return 0
