# Android 设备信息 APK

这是一个 Python + Kivy + PyJNIus 应用，启动后读取并弹窗/页面显示：

- Android 类型、版本、厂商、型号、屏幕分辨率、系统语言
- 网络类型、运营商、出口公网 IP、IP 归属城市
- GPS 经度、纬度、Android 反向地理编码得到的定位城市
- Android ID 作为设备唯一持久 ID

城市区号和行政区划代码没有统一的 Android 本地 API，当前显示“未获取（需地区编码服务）”，不会根据城市名称猜测编码。

## 在 WSL/Linux 构建

Buildozer 的 Android 工具链建议在 WSL2 Ubuntu 或 Linux 中运行：

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv git zip unzip openjdk-17-jdk
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip buildozer cython
buildozer -v android debug
```

生成的 APK 位于 `bin/` 目录。连接设备并安装：

```bash
adb install -r bin/*.apk
```

首次启动时请在 Android 权限弹窗中允许定位权限。GPS 位置依赖设备定位开关和可用定位源；公网 IP 与 IP 归属地依赖网络和 `ipinfo.io` 服务。

## Windows 构建

Windows 原生不能可靠运行完整 Buildozer Android 工具链。请在 WSL2 Ubuntu 中执行上面的构建命令，并把本目录放在 WSL 可访问的位置；也可以使用 Linux CI 构建。
