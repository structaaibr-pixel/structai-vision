"""POST /buildings/{id}/captures — imagens, vídeo, GCP e validações."""


def _img(name="foto.jpg"):
    return ("images", (name, b"fake-jpeg-bytes", "image/jpeg"))


def test_capture_with_images(client, building, fake_storage, fake_reconstruction):
    r = client.post(f"/buildings/{building.id}/captures",
                    files=[_img(f"f{i}.jpg") for i in range(5)],
                    data={"source": "phone"})
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "pending"
    assert body["image_count"] == 5
    assert body["has_video"] is False
    image_keys = [k for k in fake_storage
                  if k.startswith(f"captures/{body['id']}/images/")]
    assert len(image_keys) == 5
    assert fake_storage[image_keys[0]] == b"fake-jpeg-bytes"
    assert fake_reconstruction == [body["id"]]


def test_capture_with_video_only(client, building, fake_storage, fake_reconstruction):
    r = client.post(f"/buildings/{building.id}/captures",
                    files=[("video", ("fachada.mp4", b"fake-mp4", "video/mp4"))])
    assert r.status_code == 202
    body = r.json()
    assert body["has_video"] is True
    assert body["image_count"] == 0
    assert fake_storage[f"captures/{body['id']}/video/fachada.mp4"] == b"fake-mp4"
    assert fake_reconstruction == [body["id"]]


def test_capture_with_gcp(client, building, fake_storage):
    files = [_img(f"f{i}.jpg") for i in range(5)]
    files.append(("gcp", ("gcp_list.txt", b"EPSG:31983\n", "text/plain")))
    r = client.post(f"/buildings/{building.id}/captures", files=files)
    assert r.status_code == 202
    body = r.json()
    assert body["has_gcp"] is True
    assert fake_storage[f"captures/{body['id']}/gcp_list.txt"] == b"EPSG:31983\n"


def test_rejects_too_few_images_without_video(client, building, fake_storage,
                                              fake_reconstruction):
    r = client.post(f"/buildings/{building.id}/captures",
                    files=[_img("f1.jpg"), _img("f2.jpg")])
    assert r.status_code == 422
    assert fake_storage == {}          # nada foi salvo
    assert fake_reconstruction == []   # nada foi enfileirado


def test_rejects_unsupported_video_type(client, building, fake_reconstruction):
    r = client.post(f"/buildings/{building.id}/captures",
                    files=[("video", ("f.wmv", b"x", "video/x-ms-wmv"))])
    assert r.status_code == 422
    assert fake_reconstruction == []


def test_rejects_unsupported_image_type(client, building, fake_reconstruction):
    files = [_img(f"f{i}.jpg") for i in range(4)]
    files.append(("images", ("doc.pdf", b"%PDF", "application/pdf")))
    r = client.post(f"/buildings/{building.id}/captures", files=files)
    assert r.status_code == 422
    assert fake_reconstruction == []


def test_get_capture_status(client, building):
    created = client.post(f"/buildings/{building.id}/captures",
                          files=[_img(f"f{i}.jpg") for i in range(5)]).json()
    r = client.get(f"/captures/{created['id']}")
    assert r.status_code == 200
    assert r.json()["status"] == "pending"


def test_capture_on_foreign_building_is_404(client, db_session):
    r = client.post("/buildings/9999/captures",
                    files=[_img(f"f{i}.jpg") for i in range(5)])
    assert r.status_code == 404
