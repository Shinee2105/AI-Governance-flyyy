"""Generate a valid Excalidraw architecture diagram for the README."""

import json
import os
import random

random.seed(7)

elements = []


def add_rect(x, y, w, h, label, bg, stroke="#1971c2"):
    eid = label.replace(" ", "_") + str(random.randint(1000, 9999))
    el = {
        "id": eid,
        "type": "rectangle",
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "angle": 0,
        "strokeColor": stroke,
        "backgroundColor": bg,
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": {"type": 3},
        "seed": random.randint(1, 2**31),
        "version": 1,
        "versionNonce": random.randint(1, 2**31),
        "isDeleted": False,
        "boundElements": [{"type": "text", "id": eid + "_t"}],
        "updated": 1700000000000,
        "link": None,
        "locked": False,
    }
    elements.append(el)
    t = {
        "id": eid + "_t",
        "type": "text",
        "x": x + 8,
        "y": y + h / 2 - 10,
        "width": w - 16,
        "height": 20,
        "angle": 0,
        "strokeColor": "#1e1e1e",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 1,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": None,
        "seed": random.randint(1, 2**31),
        "version": 1,
        "versionNonce": random.randint(1, 2**31),
        "isDeleted": False,
        "boundElements": [],
        "updated": 1700000000000,
        "link": None,
        "locked": False,
        "text": label,
        "fontSize": 14,
        "fontFamily": 1,
        "textAlign": "center",
        "verticalAlign": "middle",
        "baseline": 14,
        "containerId": eid,
        "originalText": label,
    }
    elements.append(t)
    return eid


def add_arrow(x1, y1, x2, y2):
    eid = "arrow" + str(random.randint(1000, 9999))
    el = {
        "id": eid,
        "type": "arrow",
        "x": x1,
        "y": y1,
        "width": x2 - x1,
        "height": y2 - y1,
        "angle": 0,
        "strokeColor": "#868e96",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": {"type": 2},
        "seed": random.randint(1, 2**31),
        "version": 1,
        "versionNonce": random.randint(1, 2**31),
        "isDeleted": False,
        "boundElements": [],
        "updated": 1700000000000,
        "link": None,
        "locked": False,
        "startBinding": None,
        "endBinding": None,
        "startArrowhead": None,
        "endArrowhead": "arrow",
        "points": [[0, 0], [x2 - x1, y2 - y1]],
    }
    elements.append(el)


# Layout
add_rect(40, 40, 160, 60, "Browser", "#a5d8ff")
add_rect(40, 160, 160, 60, "React SPA", "#a5d8ff")
add_rect(260, 160, 200, 60, "FastAPI (REST)", "#b2f2bb")
add_rect(260, 280, 200, 60, "Connector Framework", "#b2f2bb")
add_rect(500, 280, 180, 60, "Microsoft365\nConnector", "#ffec99")
add_rect(500, 370, 180, 60, "Demo Connector", "#ffec99")
add_rect(740, 280, 200, 60, "Salesforce REST API", "#ffc9c9")
add_rect(740, 370, 200, 60, "Session Trace OTel API", "#ffc9c9")
add_rect(260, 460, 200, 60, "PostgreSQL", "#d0bfff")

# Arrows
add_arrow(120, 100, 120, 160)        # browser -> SPA
add_arrow(200, 190, 260, 190)        # SPA -> FastAPI
add_arrow(360, 220, 360, 280)        # FastAPI -> Connector framework
add_arrow(460, 310, 500, 310)        # framework -> SF conn
add_arrow(460, 340, 500, 400)        # framework -> demo conn
add_arrow(680, 310, 740, 310)        # sf -> rest api
add_arrow(680, 400, 740, 400)        # demo -> simulated (visual)
add_arrow(360, 340, 360, 460)        # framework -> db
add_arrow(360, 220, 360, 220)        # noop guard

scene = {
    "type": "excalidraw",
    "version": 2,
    "source": "https://excalidraw.com",
    "elements": elements,
    "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
    "files": {},
}

out = os.path.join(os.path.dirname(__file__), "..", "architecture.excalidraw")
out = os.path.abspath(out)
with open(out, "w") as f:
    json.dump(scene, f, indent=2)
print("wrote", out, "with", len(elements), "elements")

