import argparse
import json
import requests
from os.path import expanduser
import yaml


# silence insecure request warnings; these are generated because the hue bridge
# uses https with a self-signed certificate
requests.packages.urllib3.disable_warnings()


CONFIG_PATH = "~/.config/huedo.yaml"


class HueDoError(RuntimeError):
    pass


class HueDoConfig:
    def __init__(self):
        self.loaded = False
        self.config = {}
        self._load()

    def build_url(self, fragment):
        return f"https://{self.config['hub']['ip']}/api/{self.config['hub']['user']}/{fragment}"

    def get_lightgroup(self, group_name):
        if group_name in self.config["lightgroups"]:
            return self.config["lightgroups"][group_name]

        raise HueDoError(f"Unconfigured light group {group_name}")

    def _load(self):
        if self.loaded:
            return

        with open(expanduser(CONFIG_PATH)) as f:
            raw =  f.read()

        self.config = yaml.safe_load(raw)
        self.loaded = True


class HueDoClient:
    def __init__(self):
        self.config = HueDoConfig()

    def toggle_lightgroup(self, group_name):
        """
        Toggles all lights in the group.  Group names are set up in the config
        """
        group = self.config.get_lightgroup(group_name)
        for light in group["lights"]:
            self.toggle_light(light)

    def toggle_light(self, light):
        new_state = not self.light_is_on(light)
        self.call("PUT", f"lights/{light}/state", body={"on":new_state})

    def light_is_on(self, light):
        resp = self.call("GET", f"lights/{light}")
        return resp["state"]["on"]

    def get_lights(self):
        return self.call("GET", "lights")
    
    def call(self, method, fragment, body={}):
        func = getattr(requests, method.lower())
        url = self.config.build_url(fragment)

        body_json = None
        if body:
            body_json = json.dumps(body)

        # these certs won't verify, but it's a hue bridge on the local network,
        # so don't worry about it
        r = func(url, data=body_json, verify=False)

        if r.status_code != 200:
            raise HueDoError(f"Got unexpected response code {r.status_code}: {r.content}")

        return r.json()


def toggle_lightgroup(unparsed):
    parser = argparse.ArgumentParser()
    parser.add_argument("light_group")
    args = parser.parse_args(unparsed)


    client = HueDoClient()

    try:
        light_id = int(args.light_group)
        client.toggle_light(light_id)
    except ValueError:
        # it wasn't a light id
        client.toggle_lightgroup(args.light_group)


def list_things(unparsed):
    parser = argparse.ArgumentParser()
    parser.add_argument("thing")
    args = parser.parse_args(unparsed)

    client = HueDoClient()

    if args.thing == "lights":
        lights = client.get_lights()

        for lid, light in lights.items():
            print(f"{lid}\t{light['name']}")
    else:
        print(f"Unrecognized thing: {thing}")

DISPATCH_TABLE = {
    "toggle": toggle_lightgroup,
    "list": list_things,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command")
    parsed, unparsed = parser.parse_known_args()

    if parsed.command in DISPATCH_TABLE:
        try:
            DISPATCH_TABLE[parsed.command](unparsed)
        except HueDoError as e:
            print(f"Error: {e}")
    else:
        print(f"Unknown command: {parsed.command}")

