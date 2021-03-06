#!/usr/bin/python

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# See LICENSE for more details.


"""Connect to remote_viewer using 'Connection details' dialog.
"""

import os
import sys
import logging
import subprocess

logger = logging.getLogger(__name__)


def run(helper):
    cfg = helper.query_master("get_cfg")
    dbus = helper.query_master("get_x_var", "DBUS_SESSION_BUS_ADDRESS",
                               cfg["client_vm"])
    helper.info("Dbus: %s.", repr(dbus))
    os.environ['DBUS_SESSION_BUS_ADDRESS'] = dbus
    uri = helper.query_master("get_uri")
    helper.info("Uri: %s.", repr(uri))
    os.environ['DISPLAY'] = ":0.0"
    sys.path.append(os.path.dirname(__file__))
    try:
        # Up to this point DBUS_SESSION_BUS_ADDRESS / DISPLAY must be set.
        import rv
    except Exception as e:
        helper.info("Cannot import rv: %s.", repr(e))
        return 1
    # Fail if there is a running RV.
    try:
        rv.Application(method="mouse")
    except rv.GeneralError:
        # No running RV. Pass.
        pass
    else:
        raise Exception("Found runing RV.")
    try:
        # Exec new instance RV, without arguments. RV shows 'Connection
        # details' dialog.
        rv_p = subprocess.Popen(["remote-viewer"], shell=True)
        rv_app = rv.Application(method="mouse")
        rv_app.diag_connect.connect(uri, ticket=None)
        assert rv_app.dsp1
    except Exception as e:
        helper.info("Test failed with: %s.", repr(e))
        return 1
    helper.info("Test passed.")
    return 0
