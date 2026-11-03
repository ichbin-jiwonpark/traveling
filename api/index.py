"""Trip planner API: one Vercel Python function at /api, routed by ?r=.

Anyone holding the invite key (header X-Trip-Key, must equal ACCESS_KEY) can read
and write. Data lives in Upstash Redis:
  trips          hash  trip id -> trip JSON
  talk:<trip id> hash  message id -> message JSON
"""
import hmac
import json
import os
import re
import secrets
import time
import urllib.request
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MAX_BODY = 512 * 1024


class Upstash:
    def __init__(self, url, token):
        self.url, self.token = url.rstrip("/"), token

    def cmd(self, *args):
        req = urllib.request.Request(
            self.url,
            data=json.dumps(list(args)).encode(),
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as res:
            return json.loads(res.read())["result"]

    def hgetall(self, key):
        flat = self.cmd("HGETALL", key) or []
        return dict(zip(flat[::2], flat[1::2]))

    def hget(self, key, field):
        return self.cmd("HGET", key, field)

    def hset(self, key, field, value):
        self.cmd("HSET", key, field, value)

    def hdel(self, key, field):
        self.cmd("HDEL", key, field)

    def get(self, key):
        return self.cmd("GET", key)

    def set(self, key, value):
        self.cmd("SET", key, value)


class Memory:
    """Stand-in for Redis when running dev_server.py locally."""

    def __init__(self):
        self.d = {}

    def hgetall(self, key):
        return dict(self.d.get(key, {}))

    def hget(self, key, field):
        return self.d.get(key, {}).get(field)

    def hset(self, key, field, value):
        self.d.setdefault(key, {})[field] = value

    def hdel(self, key, field):
        self.d.get(key, {}).pop(field, None)

    def get(self, key):
        return self.d.get(key)

    def set(self, key, value):
        self.d[key] = value


def make_store():
    url = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    return Upstash(url, token) if url and token else None


STORE = make_store()

# The first itinerary, written to Redis once on the first request.
SEED = json.loads(r'''[
 {
  "currency": "€",
  "dest": "마드리드",
  "end": "2026-12-06",
  "id": "madrid-2026",
  "items": [
   {
    "cat": "식사",
    "cost": 0,
    "date": "2026-12-04",
    "end": "",
    "id": "m01",
    "memo": "",
    "place": "Starbucks, Berlin Brandenburg Airport Terminal 1",
    "time": "",
    "title": "스벅 타임"
   },
   {
    "cat": "이동",
    "cost": 0,
    "date": "2026-12-04",
    "end": "14:50",
    "id": "m02",
    "memo": "이베리아항공",
    "place": "Berlin Brandenburg Airport Terminal 1",
    "time": "11:35",
    "title": "베를린(1터미널) → 마드리드"
   },
   {
    "cat": "숙소",
    "cost": 0,
    "date": "2026-12-04",
    "end": "",
    "id": "m03",
    "memo": "2박",
    "place": "써니마드리드, Madrid",
    "time": "",
    "title": "숙소 체크인 (써니마드리드)"
   },
   {
    "cat": "관광",
    "cost": 0,
    "date": "2026-12-04",
    "end": "",
    "id": "m04",
    "memo": "",
    "place": "Puerta del Sol, Madrid",
    "time": "",
    "title": "Sol 광장"
   },
   {
    "cat": "식사",
    "cost": 0,
    "date": "2026-12-04",
    "end": "",
    "id": "m05",
    "memo": "restaurant la pampana에서 오징어 샌드위치",
    "photos": [
     {
      "credit": "Tamorlan, CC BY 3.0",
      "name": "오징어 샌드위치",
      "source": "https://commons.wikimedia.org/wiki/File:Bocadillo_de_calamares-2009.jpg",
      "url": "/photos/calamares.jpg"
     }
    ],
    "place": "La Pampana, Madrid",
    "time": "",
    "title": "타파스"
   },
   {
    "cat": "식사",
    "cost": 0,
    "date": "2026-12-04",
    "end": "",
    "id": "m06",
    "memo": "초리조를 곁들인 양송이 요리",
    "photos": [
     {
      "credit": "Tamorlan, CC BY 3.0",
      "name": "양송이 요리",
      "source": "https://commons.wikimedia.org/wiki/File:Champi%C3%B1ones_al_ajillo_(Madrid).jpg",
      "url": "/photos/champinones.jpg"
     }
    ],
    "place": "Mesón del Champiñón, Madrid",
    "time": "",
    "title": "메손 델 참피뇬"
   },
   {
    "cat": "관광",
    "cost": 0,
    "date": "2026-12-04",
    "end": "",
    "id": "m07",
    "memo": "되면 크리스마스 마켓도",
    "place": "Plaza Mayor, Madrid",
    "time": "",
    "title": "마요르 광장 구경"
   },
   {
    "cat": "관광",
    "cost": 0,
    "date": "2026-12-04",
    "end": "",
    "id": "m08",
    "memo": "",
    "place": "Mercado de San Miguel, Madrid",
    "time": "",
    "title": "산 미겔 시장 구경"
   },
   {
    "cat": "식사",
    "cost": 0,
    "date": "2026-12-05",
    "end": "",
    "id": "m09",
    "memo": "",
    "place": "",
    "time": "",
    "title": "숙소에서 조식 먹기 냠냠"
   },
   {
    "cat": "이동",
    "cost": 0,
    "date": "2026-12-05",
    "end": "10:49",
    "id": "m10",
    "memo": "",
    "place": "Estación de Madrid Puerta de Atocha, Madrid",
    "time": "10:15",
    "title": "마드리드 → 톨레도"
   },
   {
    "cat": "관광",
    "cost": 0,
    "date": "2026-12-05",
    "end": "",
    "id": "m11",
    "memo": "",
    "place": "Puente de San Martín, Toledo",
    "time": "",
    "title": "택시 타고 산 마르틴 다리"
   },
   {
    "cat": "식사",
    "cost": 0,
    "date": "2026-12-05",
    "end": "",
    "id": "m12",
    "memo": "Pisto con huevo, CARCAMUSAS, 봄바 메뉴 예쓰",
    "photos": [
     {
      "credit": "El Mono Español, CC BY-SA 4.0",
      "name": "Pisto con huevo",
      "source": "https://commons.wikimedia.org/wiki/File:Pisto_con_huevos.jpg",
      "url": "/photos/pisto.jpg"
     },
     {
      "credit": "Adriao, CC BY 3.0",
      "name": "Carcamusas",
      "source": "https://commons.wikimedia.org/wiki/File:CARCAMUSAS.JPG",
      "url": "/photos/carcamusas.jpg"
     }
    ],
    "place": "El Trébol, Toledo",
    "time": "",
    "title": "El Trébol에서 점심"
   },
   {
    "cat": "관광",
    "cost": 0,
    "date": "2026-12-05",
    "end": "",
    "id": "m13",
    "memo": "시내, 구시가지",
    "place": "Catedral de Toledo",
    "time": "",
    "title": "수도원, 톨레도 대성당 구경"
   },
   {
    "cat": "식사",
    "cost": 0,
    "date": "2026-12-05",
    "end": "",
    "id": "m14",
    "memo": "소도베르 광장 근처, 걷다 보면 있음",
    "place": "Biblioteca de Castilla-La Mancha, Toledo",
    "time": "",
    "title": "도서관 맨 꼭대기 카페"
   },
   {
    "cat": "관광",
    "cost": 0,
    "date": "2026-12-05",
    "end": "",
    "id": "m15",
    "memo": "",
    "place": "Mirador del Valle, Toledo",
    "time": "",
    "title": "택시 타고 전망대 이동"
   },
   {
    "cat": "이동",
    "cost": 0,
    "date": "2026-12-05",
    "end": "16:59",
    "id": "m16",
    "memo": "",
    "place": "Estación de Toledo, Toledo",
    "time": "16:25",
    "title": "톨레도 → 마드리드"
   },
   {
    "cat": "식사",
    "cost": 0,
    "date": "2026-12-05",
    "end": "",
    "id": "m17",
    "memo": "18:30 식당 예약함",
    "place": "La Cabaña Argentina, Madrid",
    "time": "",
    "title": "저녁 La Cabaña Argentina"
   },
   {
    "cat": "숙소",
    "cost": 0,
    "date": "2026-12-06",
    "end": "",
    "id": "m18",
    "memo": "",
    "place": "",
    "time": "",
    "title": "조식 먹고 짐 맡기기"
   },
   {
    "cat": "식사",
    "cost": 0,
    "date": "2026-12-06",
    "end": "",
    "id": "m23",
    "memo": "",
    "photos": [
     {
      "credit": "Matthew Hine, CC BY 2.0",
      "name": "츄러스 초코",
      "source": "https://commons.wikimedia.org/wiki/File:Chocolate_con_churros_-_San_Gin%C3%A9s,_Madrid.jpg",
      "url": "/photos/churros.jpg"
     }
    ],
    "place": "Chocolatería San Ginés, Madrid",
    "time": "",
    "title": "산 히네스에서 츄러스 초코 당 충전"
   },
   {
    "cat": "관광",
    "cost": 0,
    "date": "2026-12-06",
    "end": "",
    "id": "m19",
    "memo": "",
    "place": "Palacio Real de Madrid; Catedral de la Almudena, Madrid",
    "time": "",
    "title": "마드리드 왕궁 & 알무데나 대성당"
   },
   {
    "cat": "식사",
    "cost": 0,
    "date": "2026-12-06",
    "end": "",
    "id": "m20",
    "memo": "",
    "place": "Malasaña, Madrid",
    "time": "",
    "title": "말라사나 골목탐방 & 브런치"
   },
   {
    "cat": "쇼핑",
    "cost": 0,
    "date": "2026-12-06",
    "end": "",
    "id": "m21",
    "memo": "",
    "place": "",
    "time": "",
    "title": "근처에서 원하면 쇼핑"
   },
   {
    "cat": "이동",
    "cost": 0,
    "date": "2026-12-06",
    "end": "23:10",
    "id": "m22",
    "memo": "이베리아항공",
    "place": "Madrid-Barajas Airport",
    "time": "20:05",
    "title": "마드리드 → 베를린"
   }
  ],
  "name": "마드리드 여행",
  "start": "2026-12-04"
 }
]''')


def dump(obj):
    return json.dumps(obj, ensure_ascii=False)


def handle(method, path, headers, body):
    key = os.environ.get("ACCESS_KEY", "")
    if not key:
        return 500, {"error": "ACCESS_KEY 환경 변수가 설정되지 않았어요."}
    if STORE is None:
        return 500, {"error": "Redis 저장소가 연결되지 않았어요."}
    given = headers.get("X-Trip-Key") or ""
    if not hmac.compare_digest(given.encode(), key.encode()):
        return 401, {"error": "초대 링크가 맞지 않아요."}

    q = {k: v[0] for k, v in parse_qs(urlparse(path).query).items()}
    route = q.get("r")
    try:
        data = json.loads(body or b"{}")
    except ValueError:
        return 400, {"error": "잘못된 요청이에요."}
    if not isinstance(data, dict):
        return 400, {"error": "잘못된 요청이에요."}

    if route == "trips" and method == "GET":
        if not STORE.get("seeded"):
            for t in SEED:
                STORE.hset("trips", t["id"], dump(t))
            STORE.set("seeded", "1")
        return 200, {"trips": [json.loads(v) for v in STORE.hgetall("trips").values()]}

    if route == "trip":
        if method == "PUT":
            trip = data.get("trip")
            if not isinstance(trip, dict) or not ID.match(str(trip.get("id", ""))):
                return 400, {"error": "여행 정보가 올바르지 않아요."}
            STORE.hset("trips", trip["id"], dump(trip))
            return 200, {"ok": True}
        if method == "DELETE":
            tid = q.get("id", "")
            if not ID.match(tid):
                return 400, {"error": "여행 정보가 올바르지 않아요."}
            STORE.hdel("trips", tid)
            return 200, {"ok": True}

    if route == "talk":
        tid = q.get("trip", "")
        if not ID.match(tid):
            return 400, {"error": "여행 정보가 올바르지 않아요."}
        hkey = "talk:" + tid
        if method == "GET":
            msgs = sorted((json.loads(v) for v in STORE.hgetall(hkey).values()), key=lambda m: m.get("at", 0))
            return 200, {"msgs": msgs}
        if method == "POST":
            text = str(data.get("text", "")).strip()[:2000]
            if not text:
                return 400, {"error": "내용을 적어 주세요."}
            msg = {
                "id": secrets.token_hex(6),
                "text": text,
                "todo": bool(data.get("todo")),
                "done": False,
                "author": str(data.get("author", ""))[:20],
                "authorId": str(data.get("authorId", ""))[:40],
                "at": int(time.time() * 1000),
            }
            STORE.hset(hkey, msg["id"], dump(msg))
            return 200, {"msg": msg}
        mid = str(data.get("id") or q.get("id", ""))
        if not ID.match(mid):
            return 400, {"error": "메시지 정보가 올바르지 않아요."}
        raw = STORE.hget(hkey, mid)
        if raw is None:
            return 404, {"error": "이미 지워진 메시지예요."}
        msg = json.loads(raw)
        if method == "PATCH":
            msg["done"] = bool(data.get("done"))
            msg["doneBy"] = str(data.get("doneBy", ""))[:20]
            msg["doneById"] = str(data.get("doneById", ""))[:40]
            STORE.hset(hkey, mid, dump(msg))
            return 200, {"msg": msg}
        if method == "DELETE":
            if msg.get("authorId") != q.get("by"):
                return 403, {"error": "내가 쓴 메시지만 지울 수 있어요."}
            STORE.hdel(hkey, mid)
            return 200, {"ok": True}

    return 404, {"error": "없는 경로예요."}


class handler(BaseHTTPRequestHandler):
    def _run(self):
        size = int(self.headers.get("Content-Length") or 0)
        if size > MAX_BODY:
            status, out = 413, {"error": "내용이 너무 길어요."}
        else:
            body = self.rfile.read(size) if size else b""
            try:
                status, out = handle(self.command, self.path, self.headers, body)
            except Exception:
                status, out = 502, {"error": "저장소에 연결하지 못했어요. 잠시 뒤 다시 시도해 주세요."}
        raw = json.dumps(out, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    do_GET = do_PUT = do_POST = do_PATCH = do_DELETE = _run
