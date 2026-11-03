# 마드리드 여행 일정표

날짜별 일정과 친구와 함께 쓰는 "여행 전 Talk"가 있는 사이트예요.
로그인 없이, 초대 링크(`https://주소/비밀키`)를 가진 사람은 누구나 일정을 보고 고치고 Talk에 글을 쓸 수 있어요.

## 구성

- `public/index.html`: 화면 전체
- `public/photos/`: 음식 사진 (Wikimedia Commons, 출처는 화면 아래에 표시)
- `api/index.py`: 저장 서버 (Vercel Python 함수, 추가 패키지 없음)
- `dev_server.py`: 내 컴퓨터에서 미리 보기용 (Vercel에는 쓰이지 않음)

## Vercel에 올리기

1. 이 `madrid-trip` 폴더를 GitHub 새 저장소에 올려요. (GitHub 웹에서 파일을 끌어다 놓아도 돼요.)
2. Vercel에서 **Add New → Project**로 그 저장소를 가져와요. Framework Preset은 **Other**로 두고 Deploy를 눌러요.
3. 프로젝트의 **Storage** 탭에서 **Upstash for Redis**(무료 플랜 있음)를 만들고 이 프로젝트에 연결해요.
   연결하면 저장소 주소와 토큰 환경 변수가 자동으로 들어가요.
4. **Settings → Environment Variables**에 아래 값을 추가해요.
   - 이름: `ACCESS_KEY`
   - 값: 남이 짐작하기 어려운 긴 문자열. 터미널에서 만들 수 있어요.

     ```bash
     python3 -c "import secrets; print(secrets.token_urlsafe(12))"
     ```
5. **Deployments**에서 최신 배포를 **Redeploy**해서 환경 변수를 반영해요.
6. `https://프로젝트이름.vercel.app/ACCESS_KEY값` 으로 들어가요.
   한 번 들어가면 그 브라우저는 키를 기억해서 다음부터 주소만 열어도 돼요.
7. "여행 전 Talk" 탭 오른쪽 위 **친구 초대 링크 복사**를 눌러 친구에게 보내요.
   친구는 링크를 열고 Talk에서 이름만 정하면 바로 쓸 수 있어요.

처음 열면 마드리드 일정이 자동으로 저장소에 들어가요. 그 뒤로는 화면에서 고친 내용이 저장돼요.

## 알아 둘 점

- **초대 링크 = 비밀번호**예요. 링크를 받은 사람은 누구나 일정을 고칠 수 있어요.
  링크가 퍼졌다면 `ACCESS_KEY`를 새 값으로 바꾸고 Redeploy하면 예전 링크는 더 이상 열리지 않아요.
- Talk는 4초마다, 일정은 30초마다 새 내용을 불러와요.
- 이름은 각자의 브라우저에 저장돼요. 다른 기기나 브라우저로 들어가면 이름을 다시 정해야 하고, 예전에 쓴 글은 "내 글"로 표시되지 않아요.

## 내 컴퓨터에서 미리 보기

저장소 없이 메모리에 임시 저장해요. 서버를 끄면 내용이 사라져요.

```bash
python3 dev_server.py
```

그다음 http://localhost:3000/dev 를 열어요.
