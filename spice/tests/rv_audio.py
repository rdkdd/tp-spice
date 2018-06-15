#!/usr/bin/env python

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

"""This module Plays audio playback / record on guest and detect any pauses in
the audio stream.

=====
Audio
=====

Tests use ``QEMU_AUDIO_DRV=spice`` variable. Both: client and guest should have
``qemu_audio_drv = spice``. This type of card is enabled only if ``-spice``
remote desktop protocol is activated. For more info see ``/usr/libexec/qemu-kvm
--audio-help``.

Requirements for host machine
-----------------------------

- sox RPM.


Requirements for client
-----------------------

- pulseaudio


Requirements for client & guest
-------------------------------

- aplay, part of the alsa-utils.
- arecord, part of the alsa-utils.


Requirements to WAVE specimen
-----------------------------

- WAVE file must have persistent sound.
- http://linguistics.berkeley.edu/plab/guestwiki/index.php?title=Sox_in_phonetic_research
- To examine: $ sox sine1000.wav -n spectrogram


Scenario
--------

Guest or client plays a chunk of WAV file. Other side records. Recorded file is
examined for pauses.

 * record test - client plays.
 * playback test - guest plays.


Playback test::

 +-------------------------------------------------------------+------------+
 | Client VM                                                   |            |
 |  +-------------------------+                                |            |
 |  | remote-viewer (GuestVM) |                                |            |
 |  |                         |                                |            |
 |  | play -> def_out_dev ->  | -> def_out_dev->               | ->speakers |
 |  |                         |                                |            |
 |  |                         | PULSE_SOURCE=.monitor arecord  |            |
 |  +-------------------------+                                |            |
 |                                                             |            |
 +-------------------------------------------------------------+------------+

Recording test::

 +-------------------------------------------------------+------------+
 | Client VM                                             |            |
 |  +-------------------------+                          |            |
 |  | remote-viewer (GuestVM) |                          |            |
 |  |                         |                          |            |
 |  | arecord <- def_mic <-   | <- PULSE_SOURCE=.monitor |            |
 |  |                         |                          |            |
 |  |                         | play -> def_out_dev      | ->speakers |
 |  +-------------------------+                          |            |
 |                                                       |            |
 +-------------------------------------------------------+------------+

"""

import logging
import commands
import struct
import wave
import aexpect
import subprocess
from virttest import utils_misc
from spice.lib import stest
from spice.lib import utils
from spice.lib import act

SPECIMEN_FILE = "specimen.wav"
"""Autogenerated wav file servers as a specimen for tests."""

RECORDED_FILE = "recorded.wav"
"""Recorded audio."""

MAKE_WAV = "sox -b 16 -r 44100 --null -c 1 %s synth '02:20.00' sine 800" %\
    SPECIMEN_FILE
"""Command to generate WAV file."""


def verify_recording(path, cfg):
    """Tests whether something was actually recorded. Threshold is a number of
    bytes which have to be zeros, in order to record an unacceptable pause.

    Parameters
    ----------
    path: str
        Path to recorded wav file.
    cfg: spice.lib.Params
        Dictionary with the test parameters.

    Returns
    -------
    bool
        True if successful, False otherwise.
    """
    wav = wave.open(path, 'r')
    params = wav.getparams()
    logging.info("WAVE %s has: (nchannels, sampwidth, framerate, nframes, "
                 "comptype, compname) = %s", path, str(params))
    # Sample width in bytes per channel.
    bytes_per_sample = wav.getsampwidth()
    num_chns = wav.getnchannels()
    # https://docs.python.org/3/library/struct.html
    fmt = {}
    fmt['1'] = 'B'
    fmt['2'] = 'H'
    fmt['4'] = 'L'
    fmt['8'] = 'Q'
    # http://www-mmsp.ece.mcgill.ca/Documents/AudioFormats/WAVE/WAVE.html
    # Wave alway has File Byte Order: Little-endian
    frame_fmt = "<" + str(num_chns) + fmt[str(bytes_per_sample)]
    empty_frames = 0
    payload_frames = 0
    cur_frame = 0
    # tulip: (frame number, number subsequent empty frames)
    paused_sequences = []
    create_new_empty_chunk = True
    # Retrun empty string on EOF
    while True:
        string = wav.readframes(1)
        if not string:
            break
        frame = struct.unpack(frame_fmt, string)
        if any(frame):
            # Recorded frame has some data.
            payload_frames += 1
            create_new_empty_chunk = True
        else:
            # Recorded frame is empty. Silence on mic.
            empty_frames += 1
            if create_new_empty_chunk:
                # Found new silent sequnce
                paused_sequences.append((cur_frame, 1))
                create_new_empty_chunk = False
            else:
                # Silent sequnce continue
                f, g = paused_sequences[-1]
                paused_sequences[-1] = (f, g+1)
        cur_frame += 1
    logging.info("In total empty frames: %s, payload frames: %s", empty_frames,
                 payload_frames)
    # Do not count solitary empty frames. Let us assume that pause in recording
    # are more then 20 sequential empty frames.
    gen = ((f, g) for f, g in paused_sequences if g > 20)
    pauses = 0
    for f, g in gen:
        logging.info("Silence from %s frame, %s frames", f, g)
        pauses += 1
    logging.info("Total pauses: %s.", pauses)
    if payload_frames == 0:
        return bool(cfg.disable_audio)
    return True


def test(vt_test, test_params, env):
    """Playback of audio stream tests for remote-viewer.

    Parameters
    ----------
    vt_test : avocado.core.plugins.vt.VirtTest
        QEMU test object.
    test_params : virttest.utils_params.Params
        Dictionary with the test parameters.
    env : virttest.utils_env.Env
        Dictionary with test environment.

    Raises
    ------
    TestFail
        Test fails for expected behaviour.

    """
    test = stest.ClientGuestTest(vt_test, test_params, env)
    cfg = test.cfg
    act.x_active(test.vmi_c)
    act.x_active(test.vmi_g)
    ssn_c = act.new_ssn(test.vmi_c)
    ssn_g = act.new_ssn(test.vmi_g)
    # Get default sink at the client.
    cmd = r"pacmd stat | grep 'Default sink name' | " \
        r"sed -e 's/^.*[[:space:]]//'"
    try:
        def_sink = ssn_c.cmd(cmd).rstrip('\r\n')
    except aexpect.ShellCmdError as excp:
        raise utils.SpiceTestFail(test, "Test failed: %s" % str(excp))
    logging.info("Default sink at client is: %s", def_sink)
    # Create RV session
    # env = {}
    if cfg.rv_record:
        env["PULSE_SOURCE"] = "%s.monitor" % def_sink
    ssn = act.new_ssn(test.vmi_c)
    act.rv_connect(test.vmi_c, ssn)
    ret, out = commands.getstatusoutput(MAKE_WAV)
    if ret:
        errmsg = "Cannot generate specimen WAV file: %s" % out
        raise utils.SpiceTestFail(test, errmsg)
    play_cmd = "aplay %s &> /dev/null &" % cfg.audio_tgt
    rec_cmd = "arecord -d %s -f cd %s" % (cfg.audio_time,
                                          cfg.audio_rec)
    # Check test type
    if cfg.rv_record:
        logging.info("Recording test. Player is client. Recorder is guest.")
        player = ssn_c
        recorder = ssn_g
        vm_recorder = test.vm_g
        vm_player = test.vm_c
    else:
        logging.info("Playback test. Player is guest. Recorder is client.")
        env_var = "PULSE_SOURCE=%s.monitor" % def_sink
        rec_cmd = env_var + " " + rec_cmd
        player = ssn_g
        recorder = ssn_c
        vm_recorder = test.vm_c
        vm_player = test.vm_g
    vm_player.copy_files_to(SPECIMEN_FILE, cfg.audio_tgt)
    player.cmd(play_cmd)
    if cfg.config_test == "migration":
        bguest = utils_misc.InterruptedThread(test.vm_g.migrate, kwargs={})
        bguest.start()
    try:
        recorder.cmd(rec_cmd, timeout=500)
    except aexpect.ShellCmdError as excp:
        raise utils.SpiceTestFail(test, str(excp))
    if cfg.config_test == "migration":
        bguest.join()
    vm_recorder.copy_files_from(cfg.audio_rec, RECORDED_FILE)
    if not verify_recording(RECORDED_FILE, cfg):
        raise utils.SpiceTestFail(test, "Cannot verify recorded file.")
    if cfg.rv_reconnect:
        act.rv_disconnect(test.vmi_c)
        act.rv_connect(test.vmi_c, ssn)
        try:
            recorder.cmd(rec_cmd, timeout=500)
        except aexpect.ShellCmdError as excp:
            raise utils.SpiceTestFail(test, str(excp))
        vm_recorder.copy_files_from(cfg.audio_rec, RECORDED_FILE)
        if not verify_recording(RECORDED_FILE, cfg):
            raise utils.SpiceTestFail(test, "Cannot verify recorded file.")
    # Test pass


def run(vt_test, test_params, env):
    try:
        test(vt_test, test_params, env)
    finally:
        # clean up
        subprocess.check_call(["rm", "-f", SPECIMEN_FILE, RECORDED_FILE])
