import argparse
import json
import platform
import requests
from typing import List
from os.path import expanduser, isfile
import yaml

from terminaltables import SingleTable


# silence insecure request warnings; these are generated because the hue bridge
# uses https with a self-signed certificate
requests.packages.urllib3.disable_warnings()


CONFIG_PATH = "~/.config/huedo.yaml"


def print_table(data: List[List[str]], header=True) -> None:
    """
    Prints a no-borders table with an optional header row
    """
    tab = SingleTable(data)
    tab.inner_heading_row_border = header
    tab.inner_column_border = False
    tab.inner_row_border = False
    tab.outer_border = False

    print(tab.table)


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

    def update_user(self, hub_addr: str, user: str) -> None:
        """
        Saves the config with a new username
        """
        self.config['hub']['ip'] = hub_addr
        self.config['hub']['user'] = user
        self._save()

    def _load(self):
        if self.loaded:
            return

        if not isfile(expanduser(CONFIG_PATH)):
            # if unconfigured, that's fine
            self.config = {"hub": {"ip": "", "user": ""}}
            self.loaded = True
            return

        with open(expanduser(CONFIG_PATH)) as f:
            raw =  f.read()

        self.config = yaml.safe_load(raw)
        self.loaded = True

    def _save(self) -> None:
        """
        Writes out the config as it exists in memory right now
        """
        if not self.loaded:
            raise HueDoError("Attempted to save config before it was loaded!")

        print(f"Writing new config {self.config}")

        with open(expanduser(CONFIG_PATH), "w") as f:
            f.write(yaml.dump(self.config))


class HueDoClient:
    def __init__(self):
        self.config = HueDoConfig()

    def create_user(self, hub_addr: str) -> None:
        """
        Sets up a new user with the hue hub.  The hue link button must have been
        pressed before this call will work.
        """
        res = self.call("POST", "", body={"devicetype":f"huedo#{platform.system()}"}, url=f"https://{hub_addr}/api")

        if isinstance(res, list) and "success" in res[0]:
            # got a new username - sweet!
            username = res[0]['success']['username']

            self.config.update_user(hub_addr, username)
        elif isinstance(res, list) and "error" in res[0]:
            raise HueDoError(res[0]["error"]["description"])
        else:
            raise HueDoError(f"Unexpected response: {res}")


    def toggle_lightgroup(self, group_name: str) -> None:
        """
        Toggles all lights in the group.  Group names are set up in the config
        """
        group = self.config.get_lightgroup(group_name)
        for light in group["lights"]:
            self.toggle_light(light)

    def toggle_light(self, light: int) -> None:
        """
        Toggles the state of a single light
        """
        new_state = not self.light_is_on(light)
        self.call("PUT", f"lights/{light}/state", body={"on":new_state})

    def light_is_on(self, light: int) -> bool:
        """
        Returns True if the light is on, otherwise returns False
        """
        resp = self.call("GET", f"lights/{light}")
        return resp["state"]["on"]

    def get_lights(self) -> dict:
        """
        Returns all lights as a dict of id: light_dict
        """
        return self.call("GET", "lights")

    def get_light_info(self, light: int) -> dict:
        """
        Returns information about a single light
        """
        return self.call("GET", f"lights/{light}")

    def set_light_state(
            self,
            light_id: int,
            on: bool = None,
            hue: int = None,
            brightness: int = None,
            saturation: int = None
    ) -> None:
        """
        Sets the configuration of a light
        """
        state = {}

        if on is not None:
            state["on"] = on

        if hue is not None:
            state["hue"] = hue

        if brightness is not None:
            state["bri"] = brightness

        if saturation is not None:
            state["sat"] = saturation

        if not state:
            return

        print(f"Settings {light_id} to state {state}")
        self.call("PUT", f"lights/{light_id}/state", body=state)

    def call(self, method: str, fragment: str, body: dict = {}, url: str = None) -> dict:
        func = getattr(requests, method.lower())

        if url is None:
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


def init_user(unparsed: List[str]) -> None:
    """
    Sets up huedo with a new user from the hub
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("hub_ip")
    args = parser.parse_args(unparsed)

    client = HueDoClient()
    client.create_user(args.hub_ip)


def toggle_lightgroup(unparsed: List[str]) -> None:
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


def list_things(unparsed: List[str]) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("thing")
    args = parser.parse_args(unparsed)

    client = HueDoClient()

    if args.thing == "lights":
        lights = client.get_lights()

        data = [["ID", "Name"]] + [[lid, light['name']] for lid, light in lights.items()]
        print_table(data)
    else:
        print(f"Unrecognized thing: {thing}")


def show_light_details(unparsed: List[str]) -> None:
    """
    Shows the details of a single light
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("light_id")
    args = parser.parse_args(unparsed)

    client = HueDoClient()
    light = client.get_light_info(args.light_id)

    data = [
        [ "Name:", light['name'] ],
        [ "Software Version:", light['swversion'] ],
        [ "State:", "On" if light['state']['on'] else "Off" ],
        [ "Hue:", light['state'].get('hue', 'N/A') ],
        [ "Brightness:", light['state']['bri'] ],
        [ "Saturation:", light['state'].get('sat', 'N/A') ],
    ]

    print_table(data, header=False)


def set_light_state(unparsed: List[str]) -> None:
    """
    Sets the current state of a single light
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("light_id")
    parser.add_argument("--state")
    parser.add_argument("--hue", type=int)
    parser.add_argument("--brightness", type=int)
    parser.add_argument("--saturation", type=int)
    args = parser.parse_args(unparsed)

    on = None
    if args.state is not None:
        on = args.state == "on"

    client = HueDoClient()
    client.set_light_state(
        args.light_id,
        on = on,
        hue = args.hue,
        brightness = args.brightness,
        saturation = args.saturation,
    )


def raw(unparsed: List[str]) -> None:
    """
    Handles sending requests directly to the bridge.
    Accepts the fragment, JSON body, and method (default
    GET) and prints out the JSON response.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("fragment")
    parser.add_argument("method", nargs="?", default="GET")
    parser.add_argument("body", nargs="?", default="{}")
    args = parser.parse_args(unparsed)

    try:
        body = json.loads(args.body)
    except JSONDecodeError:
        print("Body specified must be valid JSON!")
        exit(1)

    client = HueDoClient()
    res = client.call(args.method, args.fragment, body)

    print(json.dumps(res))

DISPATCH_TABLE = {
    "init": init_user,
    "toggle": toggle_lightgroup,
    "list": list_things,
    "show": show_light_details,
    "set": set_light_state,
    "raw": raw,
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

