# Copyright (C) 2022 - 2024 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Miscellaneous embedding tests"""
import os
import subprocess
import sys
from tempfile import NamedTemporaryFile
import time

import pytest

import ansys.mechanical.core.embedding.utils as utils


@pytest.mark.embedding
def test_app_repr(embedded_app):
    """Test repr of the Application class."""
    app_repr_lines = repr(embedded_app).splitlines()
    assert app_repr_lines[0].startswith("Ansys Mechanical")
    assert app_repr_lines[1].startswith("Product Version")
    assert app_repr_lines[2].startswith("Software build date:")


@pytest.mark.embedding
@pytest.mark.minimum_version(241)
def test_deprecation_warning(embedded_app):
    harmonic_acoustic = embedded_app.Model.AddHarmonicAcousticAnalysis()
    with pytest.warns(UserWarning):
        harmonic_acoustic.SystemID
    with pytest.warns(UserWarning):
        harmonic_acoustic.AnalysisSettings.MultipleRPMs = True


@pytest.mark.embedding
def test_app_save_open(embedded_app, tmp_path: pytest.TempPathFactory):
    """Test save and open of the Application class."""
    import System
    import clr  # noqa: F401

    # save without a save_as throws an exception
    with pytest.raises(System.Exception):
        embedded_app.save()

    embedded_app.DataModel.Project.Name = "PROJECT 1"
    project_file = os.path.join(tmp_path, f"{NamedTemporaryFile().name}.mechdat")
    embedded_app.save_as(project_file)
    embedded_app.new()
    embedded_app.open(project_file)
    assert embedded_app.DataModel.Project.Name == "PROJECT 1"
    embedded_app.DataModel.Project.Name = "PROJECT 2"
    embedded_app.save()
    embedded_app.new()
    embedded_app.open(project_file)
    assert embedded_app.DataModel.Project.Name == "PROJECT 2"
    embedded_app.new()


@pytest.mark.embedding
def test_app_update_globals_after_open(embedded_app, assets):
    """Test save and open of the Application class."""
    embedded_app.update_globals(globals())
    # unless the global "Model" has been redirected to point to the new model from the project file
    # this will throw an exception
    embedded_app.new()
    embedded_app.open(os.path.join(assets, "cube-hole.mechdb"))
    Model.AddNamedSelection()


@pytest.mark.embedding
def test_app_version(embedded_app):
    """Test version of the Application class."""
    version = embedded_app.version
    assert type(version) is int
    assert version >= 232


@pytest.mark.embedding
def test_nonblock_sleep(embedded_app):
    """Test non-blocking sleep."""
    t1 = time.time()
    utils.sleep(1000)
    t2 = time.time()
    assert (t2 - t1) >= 1


@pytest.mark.embedding
def test_app_print_tree(embedded_app, capsys, assets):
    """Test printing hierarchical tree of Mechanical ExtAPI object"""
    embedded_app.update_globals(globals())
    geometry_file = os.path.join(assets, "Eng157.x_t")
    geometry_import = Model.GeometryImportGroup.AddGeometryImport()
    geometry_import.Import(geometry_file)
    allbodies = Model.GetChildren(DataModelObjectCategory.Body, True)
    allbodies[0].Suppressed = True
    embedded_app.print_tree()
    captured = capsys.readouterr()
    printed_output = captured.out.strip()
    assert "Project" in printed_output
    assert "Suppressed" in printed_output

    embedded_app.print_tree(max_lines=2)
    captured = capsys.readouterr()
    printed_output = captured.out.strip()
    assert "Model" in printed_output
    assert "truncating after" in printed_output

    with pytest.raises(AttributeError):
        embedded_app.print_tree(DataModel)


@pytest.mark.embedding
def test_app_poster(embedded_app):
    """The getters of app should be usable after a new().

    The C# objects referred to by ExtAPI, Model, DataModel, and Tree
    are reset on each call to app.new(), so storing them in
    global variables will be broken.

    To resolve this, we have to wrap those objects, and ensure
    that they properly redirect the calls to the appropriate C#
    object after a new()
    """
    version = embedded_app.version
    if os.name != "nt" and version < 242:
        """This test is effectively disabled for versions older than 242 on linux.

        This is because the function coded is distributed with the C# library
        Ansys.Mechanical.CPython.dll. That library only began to be shipping on
        linux in 2024 R2.
        """
        return
    poster = embedded_app.poster

    name = []

    def change_name_async(poster):
        """Change_name_async will run a background thread

        It will change the name of the project to "foo"
        """

        def get_name():
            return embedded_app.DataModel.Project.Name

        def change_name():
            embedded_app.DataModel.Project.Name = "foo"

        name.append(poster.post(get_name))
        poster.post(change_name)

    import threading

    change_name_thread = threading.Thread(target=change_name_async, args=(poster,))
    change_name_thread.start()

    # The poster can't do anything unless the main thread is receiving
    # messages. The `sleep` utility puts Mechanical's main thread to
    # idle and only execute actions that have been posted to its main
    # thread, e.g. `change_name` that was posted by the poster.
    utils.sleep(400)
    change_name_thread.join()
    assert len(name) == 1
    assert name[0] == "Project"
    assert embedded_app.DataModel.Project.Name == "foo"


@pytest.mark.embedding
def test_app_getters_notstale(embedded_app):
    """The getters of app should be usable after a new().

    The C# objects referred to by ExtAPI, Model, DataModel, and Tree
    are reset on each call to app.new(), so storing them in
    global variables will be broken.

    To resolve this, we have to wrap those objects, and ensure
    that they properly redirect the calls to the appropriate C#
    object after a new()
    """
    data_model = embedded_app.DataModel
    data_model.Project.Name = "a"
    model = embedded_app.Model
    model.Name = "b"
    embedded_app.new()
    assert data_model.Project.Name != "a"
    assert model.Name != "b"


@pytest.mark.embedding_scripts
@pytest.mark.python_env
def test_warning_message(test_env, pytestconfig, run_subprocess, rootdir):
    """Test Python.NET warning of the embedded instance using a test-scoped Python environment."""

    # Install pymechanical
    subprocess.check_call(
        [test_env.python, "-m", "pip", "install", "-e", "."],
        cwd=rootdir,
        env=test_env.env,
    )

    # Install pythonnet
    subprocess.check_call([test_env.python, "-m", "pip", "install", "pythonnet"], env=test_env.env)

    # Run embedded instance in virtual env with pythonnet installed
    embedded_py = os.path.join(rootdir, "tests", "scripts", "run_embedded_app.py")
    _, stderr = run_subprocess(
        [test_env.python, embedded_py, pytestconfig.getoption("ansys_version")]
    )

    # If UserWarning & pythonnet are in the stderr output, set warning to True.
    # Otherwise, set warning to False
    warning = True if "UserWarning" and "pythonnet" in stderr.decode() else False

    # Assert warning message appears for embedded app
    assert warning, "UserWarning should appear in the output of the script"


@pytest.mark.embedding_scripts
@pytest.mark.python_env
def test_private_appdata(pytestconfig, run_subprocess, rootdir):
    """Test embedded instance does not save ShowTriad using a test-scoped Python environment."""

    version = pytestconfig.getoption("ansys_version")
    embedded_py = os.path.join(rootdir, "tests", "scripts", "run_embedded_app.py")

    run_subprocess([sys.executable, embedded_py, version, "True", "Set"])
    stdout, _ = run_subprocess([sys.executable, embedded_py, version, "True", "Run"])
    stdout = stdout.decode()
    assert "ShowTriad value is True" in stdout


@pytest.mark.embedding_scripts
@pytest.mark.python_env
def test_normal_appdata(pytestconfig, run_subprocess, rootdir):
    """Test embedded instance saves ShowTriad value using a test-scoped Python environment."""
    version = pytestconfig.getoption("ansys_version")

    embedded_py = os.path.join(rootdir, "tests", "scripts", "run_embedded_app.py")

    run_subprocess([sys.executable, embedded_py, version, "False", "Set"])
    stdout, _ = run_subprocess([sys.executable, embedded_py, version, "False", "Run"])
    run_subprocess([sys.executable, embedded_py, version, "False", "Reset"])

    stdout = stdout.decode()
    # Assert ShowTriad was set to False for regular embedded session
    assert "ShowTriad value is False" in stdout


@pytest.mark.embedding_scripts
def test_building_gallery(pytestconfig, run_subprocess, rootdir):
    """Test for building gallery check.

    When building the gallery, each example file creates another instance of the app.
    When the BUILDING_GALLERY flag is enabled, only one instance is kept.
    This is to test the bug fixed in https://github.com/ansys/pymechanical/pull/784
    and will fail on PyMechanical version 0.11.0
    """
    version = pytestconfig.getoption("ansys_version")

    embedded_gallery_py = os.path.join(rootdir, "tests", "scripts", "build_gallery_test.py")

    _, stderr = run_subprocess([sys.executable, embedded_gallery_py, version, "False"], None, False)
    stderr = stderr.decode()

    # Assert Exception
    assert "Cannot have more than one embedded mechanical instance" in stderr

    stdout, _ = run_subprocess([sys.executable, embedded_gallery_py, version, "True"])
    stdout = stdout.decode()

    # Assert stdout after launching multiple instances
    assert "Multiple App launched with building gallery flag on" in stdout


@pytest.mark.embedding
def test_shims_import_material(embedded_app, assets):
    """Test deprecation warning for shims import material."""
    from ansys.mechanical.core.embedding import shims

    embedded_app.update_globals(globals())
    material_file = os.path.join(assets, "eng200_material.xml")
    with pytest.warns(DeprecationWarning):
        shims.import_materials(embedded_app, material_file)


@pytest.mark.embedding
def test_rm_lockfile(embedded_app, tmp_path: pytest.TempPathFactory):
    """Test lock file is removed on close of embedded application."""
    mechdat_path = os.path.join(tmp_path, "test.mechdat")
    embedded_app.save(mechdat_path)
    embedded_app.close()

    lockfile_path = os.path.join(embedded_app.DataModel.Project.ProjectDirectory, ".mech_lock")
    # Assert lock file path does not exist
    assert not os.path.exists(lockfile_path)


@pytest.mark.embedding
def test_app_execute_script(embedded_app):
    """Test execute_script method."""
    embedded_app.update_globals(globals())
    result = embedded_app.execute_script("2+3")
    assert result == 5
    with pytest.raises(Exception):
        # This will throw an exception since no module named test available
        embedded_app.execute_script("import test")
