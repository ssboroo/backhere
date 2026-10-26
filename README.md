# BackHere — Windows Desktop

**Ажлаа яг хаана орхисноо хадгалаад, дараа нь шууд үргэлжлүүл.**

Windows 10/11 x64-д зориулсан native desktop апп. Вебсайт биш. Бүртгэл, сервер, subscription шаардлагагүй.

## Ажиллуулах

### Суулгагч / portable EXE

GitHub → **Actions → Windows desktop build → амжилттай run → Artifacts → BackHere-Windows-x64** татаж задлана.

- `BackHere-Setup-0.1.0.exe`: хэрэглэгчийн Programs хавтсанд суулгана, Start Menu/Desktop shortcut үүсгэнэ. Admin эрх шаардахгүй.
- `BackHere.exe`: Python суулгахгүйгээр шууд ажиллах portable файл. Өгөгдөл нь USB дээр бус, тухайн Windows хэрэглэгчийн AppData-д хадгалагдана.

Эдгээр файлыг Windows CI build амжилттай болсон үед artifact-аас татна. Unsigned build тул Windows SmartScreen анхааруулга гарч болно; release code signing одоогоор хийгдээгүй.

### Source-оос

Python 3.12+ (Tcl/Tk, Python launcher-тай) суулгаад **Run-BackHere.bat** давхар дарна. Runtime dependency байхгүй.

```powershell
py -3 desktop\backhere.py
```

Өөрөө EXE бүтээх:

```powershell
powershell -ExecutionPolicy Bypass -File .\Build-Windows.ps1
```

Эсвэл PowerShell скрипт хэрэглэхгүйгээр:

```powershell
py -3 -m pip install -r requirements-build.txt
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name BackHere --add-data "desktop/locales.json;." desktop/backhere.py
```

Inno Setup 6 ашиглан `installer.iss` compile хийж суулгагч гаргана.

## Үндсэн урсгал

1. Аппыг ажиллуулж, нээлттэй эсвэл minimized байлгана.
2. Өөр программ дээр **Ctrl+Alt+B** дарна. BackHere нээгдэж одоогийн цонхны гарчгийг оруулна.
3. File Explorer-т файл сонгосон бол тухайн замыг Shell COM-оор авна. Бусад программын документын зам/браузерын URL-ийг энэ хувилбарт гараар оруулна. `…` товчоор файл сонгож болно.
4. «Дараа нь хүснэгтийн 3-р баганыг шалга» гэж бичээд **Ctrl+Enter** дарж хадгална.
5. Жагсаалтаас сонгоод **Үргэлжлүүлэх** эсвэл давхар дарахад файл default программаараа, URL default браузераар нээгдэнэ.
6. Дууссан ажлаа нэг дараад хаана; Дууссан хэсгээс сэргээж болно.

**Ctrl+N:** шинэ тэмдэглэл. **Ctrl+F:** хайлт. **Ctrl+Alt+B:** бусад цонхноос шинэ тэмдэглэл. Shortcut өөр апптай давхцвал статус дээр мэдэгдэнэ. Апп бүрэн хаалттай үед shortcut ажиллахгүй.

## Боломжууд

- Файл/URL, богино тэмдэглэл, төсөл, байрлал
- SQLite хадгалалт: `%LOCALAPPDATA%\BackHere\backhere.sqlite3`
- Хайлт, онцлох, шинэ/хуучнаар эрэмбэлэх (хүснэгтийн гарчиг дээр дарах)
- Дуусгах, сэргээх; зөвхөн дууссан тэмдэглэлийг баталгаажуулж устгана
- JSON экспорт/импорт, давхардлыг ID-аар алгасана; буруу нөөц бүхэлдээ цуцлагдана
- Монгол, English, Español, Français, Deutsch, Русский, 中文, 日本語, 한국어, Português, Türkçe, العربية
- DPI awareness, цонхны хэмжээнд уян хүснэгт, keyboard navigation
- Telemetry, analytics, cloud sync, AI API байхгүй

## Одоогийн хязгаар

- v0.1 MVP. Windows дээрх CI build, UI smoke test болон бодит хэрэглэгчийн туршилтаар баталгаажуулна.
- Браузерын URL/Word/Excel-ийн документын замыг автоматаар танихгүй; гараар оруулна. Explorer сонголт л автоматаар орно.
- Excel cell, Word page, scroll зэрэг байрлал гараар харах тэмдэглэл байна. Тоон байрлалтай веб PDF-д `#page=N` нэмж өгнө; viewer-ээс хамаарна. Native PDF-ийн яг хуудсыг автоматаар нээхгүй.
- 12 хэлний үндсэн UI орсон. Windows error text болон зарим техникийн status англи; Arabic нь Unicode дэмжинэ, бүрэн RTL layout хараахан байхгүй. Native speaker review шаардлагатай.
- Tray icon, Windows startup, auto-update, cloud sync, лиценз/төлбөр болон code signing хараахан байхгүй.
- SQLite болон экспорт шифрлээгүй. Нөөцөө өөрөө хадгална. Uninstall нь хэрэглэгчийн database-ийг зориуд устгахгүй.
- Shortcut нэг ажиллаж буй instance-д бүртгэгдэнэ. Давхар ажиллуулбал хоёр дахь instance shortcut зөрчилтэйг мэдээлнэ.
- Нэг удаагийн $15–25 худалдаанд гаргахын өмнө signing, installer QA, recovery/backup QA, лиценз, accessibility болон locale review гүйцээнэ.

## Шалгалт

```powershell
py -3 -m unittest discover -s tests -v
py -3 tests\smoke_ui.py
```

Core тестүүд хадгалалт/дахин нээх, засвар, дуусгах/сэргээх, backup merge/atomic validation, protocol хамгаалалт, PDF URL, 12 хэлний бүрэн байдлыг шалгана. UI smoke нь Windows CI дээр ажиллана. Native shortcut/Explorer capture-г бодит Windows дээр тусад нь туршина.
