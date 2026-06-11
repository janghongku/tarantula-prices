# -*- coding: utf-8 -*-
"""공유 유틸 — 여러 스크립트가 같은 로직을 복붙하던 것을 한 곳으로.
⚠ 특히 hist_key는 price_history.json의 '키'다. 이게 파일마다 다르면 가격이력 링크가
조용히 끊긴다. 절대 복제하지 말고 여기서만 import 할 것."""
import os
import re
import tempfile


def hist_key(url):
    """가격이력 안정키 — 상품명/슬러그가 바뀌어도 같은 상품번호면 이력이 안 끊긴다.
    네이버 .../products/{pid}, 자사몰 .../product/{슬러그}/{번호}/ 에서 번호 추출."""
    u = url or ""
    host = re.sub(r"^https?://", "", u).split("/")[0]
    if not host:
        return u
    m = re.search(r"/products/(\d+)", u) or re.search(r"/product/[^/]+/(\d+)", u)
    return f"{host}/{m.group(1)}" if m else u


def won(n):
    """가격 천단위 콤마 표기."""
    return f"{int(n):,}"


def atomic_write(path, content):
    """임시파일에 쓴 뒤 os.replace로 원자적 교체. 쓰기 도중 크래시/강제종료(SIGTERM)·
    디스크풀에도 원본(특히 price_history.json)이 손상되지 않는다. 같은 디렉터리에
    임시파일을 만들어 rename이 원자적이도록 보장."""
    path = str(path)
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
