from harborflow import Route, END


def test_route_to_to_command():
    route = Route.to("node", x=1)
    cmd = route.to_command()
    assert getattr(cmd, "goto", None) == "node"
    assert getattr(cmd, "update", None) == {"x": 1}


def test_route_finish_end():
    route = Route.finish(msg="hi")
    assert route.goto is END
    assert route.update == {"msg": "hi"}