# huedo

Make Phillips Hue lights do things.

## Using as a Command

### Setup

Install from source by cloning this repository and running the following in the
root of it:

```bash
pip install -e .
```

### Usage

Before you start, find your Phillips Hue hub's IP address (it's visible in the
app), press the "sync" button (the big one on top), and run:

```bash
huedo init $HUB_IP
```

Once this is done, `~/.config/huedo.yaml` will have been created with credentials
to your hub - now you're ready to go.

To list lights, try out:

```bash
huedo list lights
```

To control lights, try:

```bash
huedo toggle $LIGHT_ID
```

## Using as a Library

Follow the setup steps above; at present you need to have a config file with
a credential to your bridge present on your system.

Once that's done, you can import and use the client:

```python
from huedo import HueDoClient

# this assumes you've
c = HueDoClient()

# find all lights known to the bridge
r = c.get_lights()

# toggle the state of the first light
c.toggle_light(list(r.keys())[0])

# make a call directly to the bridge at API base url
r = c.call("GET", "")
```
