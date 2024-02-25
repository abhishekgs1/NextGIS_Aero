from base64 import b64encode

import pytest
import transaction

from nextgisweb.env import DBSession
from nextgisweb.lib.geometry import Geometry

from nextgisweb.vector_layer.model import VectorLayer, VectorLayerField

from ..feature import Feature

pytestmark = pytest.mark.usefixtures("ngw_resource_defaults", "ngw_auth_administrator")


@pytest.fixture(scope="module")
def mkres():
    def _mkres(versioning):
        with transaction.manager:
            obj = VectorLayer(geometry_type="POINTZ").persist()
            obj.fields = [VectorLayerField(keyname="foo", datatype="STRING", display_name="foo")]
            obj.fversioning_configure(enabled=versioning)

            for i in (1, 2):
                feat = Feature(geom=Geometry.from_wkt(f"POINT Z (0 0 {i})"))
                feat.fields["foo"] = "Original"
                obj.feature_create(feat)

            DBSession.flush()
            epoch = obj.fversioning.epoch if versioning else None

        return obj.id, epoch

    yield _mkres


def wkb64(wkt):
    return b64encode(Geometry.from_wkt(wkt).wkb).decode("ascii")


def ptz(x, y, z):
    return wkb64(f"POINT Z ({x} {y} {z})")


@pytest.mark.parametrize(
    "versioning",
    [
        pytest.param(False, id="versioning_disabled"),
        pytest.param(True, id="versioning_enabled"),
    ],
)
def test_basic(versioning, mkres, ngw_webtest_app):
    (res, epoch), web = mkres(versioning), ngw_webtest_app
    txn_create = dict(epoch=epoch) if versioning else dict()

    burl = f"/api/resource/{res}/feature/transaction"
    furl = f"/api/resource/{res}/feature"

    resp = web.post_json(f"{burl}/", txn_create).json
    txn_id = resp.pop("id", None)
    assert txn_id > 0
    turl = f"{burl}/{txn_id}"

    op_1 = [1, _create(geom=ptz(0, 0, 3), fields=dict(foo="Inserted"))]
    resp = web.put_json(turl, [op_1])

    # Repeats of the same data should also report 200 OK
    resp = web.put_json(turl, [op_1])

    # But another operation should report 409 Conflict
    op_1 = [1, _delete(fid=1)]
    data = [op_1]
    resp = web.put_json(turl, data, status=409)

    # Update the first and delete the second
    op_2 = [2, _update(fid=1, geom=ptz(1, 1, 1), fields=dict(foo="Updated"))]
    op_3 = [3, _delete(fid=2)]
    web.put_json(turl, [op_2, op_3])

    # Results aren't available until commit happens
    web.get(turl, status=422)

    # Now commit the transaction twice, it's safe
    resp_a = web.post(turl).json
    resp_b = web.post(turl).json
    assert resp_a == resp_b

    # Fetch the results
    resp = web.get(turl, status=200).json
    assert resp == [
        [1, _create(fid=3)],
        [2, _update()],
        [3, _delete()],
    ]

    # Validate resource features
    resp_c = web.get(f"{furl}/?extensions=", status=200).json
    assert len(resp_c) == 2

    resp_1 = web.get(f"{furl}/1?extensions=", status=200).json
    assert resp_1 == dict(id=1, geom="POINT Z (1 1 1)", fields=dict(foo="Updated"))

    resp_2 = web.get(f"{furl}/2?extensions=", status=404).json
    assert "title" in resp_2 and "message" in resp_2

    resp_3 = web.get(f"{furl}/3?extensions=", status=200).json
    assert resp_3 == dict(id=3, geom="POINT Z (0 0 3)", fields=dict(foo="Inserted"))

    # Dispose transaction
    web.delete(turl, status=200)
    web.get(turl, status=404)


@pytest.mark.parametrize(
    "versioning",
    [
        pytest.param(False, id="versioning_disabled"),
        pytest.param(True, id="versioning_enabled"),
    ],
)
def test_errors(versioning, mkres, ngw_webtest_app):
    (res, epoch), web = mkres(versioning), ngw_webtest_app
    txn_create = dict(epoch=epoch) if versioning else dict()

    burl = f"/api/resource/{res}/feature/transaction"
    furl = f"/api/resource/{res}/feature"

    resp = web.post_json(f"{burl}/", txn_create).json
    txn_id = resp.pop("id", None)
    assert txn_id > 0
    turl = f"{burl}/{txn_id}"

    op_1 = [1, _update(fid=3, fields=dict(foo="Updated"))]
    op_2 = [2, _update(fid=4, fields=dict(foo="Omitted"))]
    resp = web.put_json(turl, [op_1, op_2])

    # Commit should report errors
    resp_a = web.post(turl).json
    assert resp_a["status"] == "errors"
    assert len(resp_a["errors"]) == 2

    first_error = dict(resp_a["errors"][0][1])
    first_error.pop("message")
    assert first_error == dict(error="feature.not_found", status_code=404)

    # Repeated commits should report the same
    resp_b = web.post(turl).json
    assert resp_a == resp_b

    # Results are not available
    web.get(turl, status=422)

    # Fix the first, drop the second, and commit
    op_1 = [1, _update(fid=1, fields=dict(foo="Updated"))]
    op_2 = [2, None]
    web.put_json(turl, [op_1, op_2])
    resp = web.post(turl).json
    assert resp["status"] == "committed"

    # Read results
    resp = web.get(turl, status=200).json
    assert resp == [[1, _update()]]

    # Validate
    resp_1 = web.get(f"{furl}/1?extensions=", status=200).json
    assert resp_1 == dict(id=1, geom="POINT Z (0 0 1)", fields=dict(foo="Updated"))

    # Dispose transaction
    web.delete(turl, status=200)
    web.get(turl, status=404)

    if versioning:
        resp = web.post_json(f"{burl}/", txn_create).json
        txn_id = resp.pop("id", None)
        turl = f"{burl}/{txn_id}"

        # The 1st feature was changed in 2nd version
        op_1 = [1, _update(fid=1, vid=1, fields=dict(foo="Updated"))]
        web.put_json(turl, [op_1])

        resp = web.post(turl).json
        assert resp["status"] == "errors"
        assert len(resp["errors"]) == 1
        assert resp["errors"][0][1]["error"] == "feature.conflict"

        op_1 = [1, _update(fid=1, vid=2, fields=dict(foo="Updated"))]
        web.put_json(turl, [op_1])

        resp = web.post(turl).json
        assert resp["status"] == "committed"


_create = lambda **kwargs: dict(action="feature.create", **kwargs)
_update = lambda **kwargs: dict(action="feature.update", **kwargs)
_delete = lambda **kwargs: dict(action="feature.delete", **kwargs)
