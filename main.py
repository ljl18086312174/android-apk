from __future__ import annotations

import json
import threading
import urllib.request
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.boxlayout import BoxLayout


try:
    from android.permissions import Permission, check_permission, request_permissions
    ANDROID = True
except ImportError:
    ANDROID = False


class DeviceInfoApp(App):
    title = "设备信息"

    def build(self):
        Window.clearcolor = (0.96, 0.97, 0.98, 1)
        root = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))
        self.output = Label(
            text="正在读取设备信息...",
            color=(0.10, 0.12, 0.15, 1),
            halign="left",
            valign="top",
            text_size=(None, None),
            size_hint_y=None,
            padding=(dp(10), dp(10)),
        )
        self.info_popup = None
        self.output.bind(texture_size=self._resize_output)
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(self.output)
        root.add_widget(scroll)
        refresh = Button(text="重新获取", size_hint_y=None, height=dp(48))
        refresh.bind(on_release=lambda *_: self.start_collection())
        root.add_widget(refresh)
        Clock.schedule_once(lambda *_: self.start_collection(), 0.2)
        return root

    def _resize_output(self, label, size):
        label.height = max(size[1], dp(400))
        label.text_size = (self.root.width - dp(28), None)

    def start_collection(self):
        if ANDROID:
            permissions = [
                Permission.ACCESS_FINE_LOCATION,
                Permission.ACCESS_COARSE_LOCATION,
                Permission.ACCESS_NETWORK_STATE,
                Permission.READ_PHONE_STATE,
            ]
            missing = [p for p in permissions if not check_permission(p)]
            if missing:
                request_permissions(missing, self._permissions_result)
                self.set_output("请在系统弹窗中允许定位和网络相关权限，随后会自动刷新。")
                return
        self.set_output("正在读取设备信息...\n定位与公网 IP 查询可能需要几秒钟。")
        threading.Thread(target=self.collect_info, daemon=True).start()

    def _permissions_result(self, permissions, grants):
        Clock.schedule_once(lambda *_: self.start_collection(), 0.3)

    def collect_info(self):
        info = collect_android_info() if ANDROID else {"运行环境": "桌面 Python（请在 Android APK 中运行）"}
        info["采集时间"] = datetime.now().astimezone().isoformat(timespec="seconds")
        public = get_public_ip_info()
        info.update(public)
        location = get_location_info()
        info.update(location)
        text = "\n".join(f"{key}：{value}" for key, value in info.items())
        Clock.schedule_once(lambda *_: self.set_output(text), 0)

    def set_output(self, text):
        self.output.text = text
        self.output.texture_update()
        self._resize_output(self.output, self.output.texture_size)
        if text.startswith("正在") or text.startswith("请在"):
            return
        self.show_info_popup(text)

    def show_info_popup(self, text):
        content = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(8))
        details = Label(
            text=text,
            color=(0.10, 0.12, 0.15, 1),
            halign="left",
            valign="top",
            size_hint_y=None,
            padding=(dp(8), dp(8)),
        )
        details.bind(texture_size=lambda label, size: setattr(label, "height", size[1]))
        details.text_size = (dp(320), None)
        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(details)
        content.add_widget(scroll)
        close = Button(text="关闭", size_hint_y=None, height=dp(44))
        content.add_widget(close)
        popup = Popup(
            title="设备信息",
            content=content,
            size_hint=(0.94, 0.82),
            auto_dismiss=False,
        )
        close.bind(on_release=popup.dismiss)
        if self.info_popup:
            self.info_popup.dismiss()
        self.info_popup = popup
        popup.open()


def collect_android_info():
    from jnius import autoclass

    Build = autoclass("android.os.Build")
    Version = autoclass("android.os.Build$VERSION")
    SettingsSecure = autoclass("android.provider.Settings$Secure")
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    context = PythonActivity.mActivity
    resolver = context.getContentResolver()

    metrics = context.getResources().getDisplayMetrics()
    width = metrics.widthPixels
    height = metrics.heightPixels
    density = metrics.density

    locale = context.getResources().getConfiguration().getLocales().get(0)
    language = str(locale.toLanguageTag()) if hasattr(locale, "toLanguageTag") else str(locale)
    android_id = str(SettingsSecure.getString(resolver, SettingsSecure.ANDROID_ID) or "未知")

    return {
        "操作系统类型": "Android",
        "系统版本": str(Version.RELEASE),
        "设备型号": str(Build.MODEL),
        "设备厂商": str(Build.MANUFACTURER),
        "屏幕分辨率": f"{width} x {height} px",
        "屏幕密度": f"{density:.2f}x",
        "系统语言": language,
        "网络类型": get_network_type(context),
        "运营商": get_carrier_name(context),
        "设备唯一持久 ID": android_id,
        "ID 说明": "Android ID；恢复出厂设置、用户切换或系统策略可能改变",
    }


def get_network_type(context):
    from jnius import autoclass

    ConnectivityManager = autoclass("android.net.ConnectivityManager")
    NetworkCapabilities = autoclass("android.net.NetworkCapabilities")
    manager = context.getSystemService(context.CONNECTIVITY_SERVICE)
    network = manager.getActiveNetwork()
    if network is None:
        return "无网络"
    caps = manager.getNetworkCapabilities(network)
    if caps is None:
        return "未知"
    if caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI):
        return "Wi-Fi"
    if caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR):
        return "移动网络"
    if caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET):
        return "以太网"
    return "其他"


def get_carrier_name(context):
    from jnius import autoclass

    TelephonyManager = autoclass("android.telephony.TelephonyManager")
    manager = context.getSystemService(context.TELEPHONY_SERVICE)
    name = manager.getNetworkOperatorName()
    return str(name) if name else "未知"


def get_public_ip_info():
    try:
        request = urllib.request.Request(
            "https://ipinfo.io/json",
            headers={"User-Agent": "DeviceInfoApp/1.0"},
        )
        with urllib.request.urlopen(request, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
        return {
            "出口公网 IP": data.get("ip", "未知"),
            "IP 归属城市": data.get("city", "未知"),
            "IP 归属地区": data.get("region", "未知"),
        }
    except Exception as exc:
        return {"出口公网 IP": "获取失败（请检查网络）", "IP 归属城市": "未知", "IP 查询错误": str(exc)}


def get_location_info():
    if not ANDROID:
        return {"GPS 经度": "未知", "GPS 纬度": "未知", "定位城市": "未知", "城市区号": "未获取", "行政区划代码": "未获取"}
    try:
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        LocationManager = autoclass("android.location.LocationManager")
        context = PythonActivity.mActivity
        manager = context.getSystemService(context.LOCATION_SERVICE)
        location = manager.getLastKnownLocation(LocationManager.GPS_PROVIDER)
        if location is None:
            location = manager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)
        if location is None:
            return {"GPS 经度": "暂无定位", "GPS 纬度": "暂无定位", "定位城市": "暂无定位", "城市区号": "未获取", "行政区划代码": "未获取"}

        latitude = float(location.getLatitude())
        longitude = float(location.getLongitude())
        city = reverse_geocode(latitude, longitude)
        return {
            "GPS 经度": f"{longitude:.6f}",
            "GPS 纬度": f"{latitude:.6f}",
            "定位城市": city,
            "城市区号": "未获取（需地区编码服务）",
            "行政区划代码": "未获取（需地区编码服务）",
        }
    except Exception as exc:
        return {"GPS 经度": "获取失败", "GPS 纬度": "获取失败", "定位城市": "获取失败", "城市区号": "未获取", "行政区划代码": "未获取", "定位错误": str(exc)}


def reverse_geocode(latitude, longitude):
    try:
        from jnius import autoclass

        Geocoder = autoclass("android.location.Geocoder")
        Locale = autoclass("java.util.Locale")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        geocoder = Geocoder(PythonActivity.mActivity, Locale.getDefault())
        addresses = geocoder.getFromLocation(latitude, longitude, 1)
        if addresses and addresses.size() > 0:
            address = addresses.get(0)
            locality = address.getLocality()
            admin = address.getAdminArea()
            values = [str(value) for value in (locality, admin) if value]
            return "，".join(dict.fromkeys(values)) or "未知"
    except Exception:
        pass
    return "未知"


if __name__ == "__main__":
    DeviceInfoApp().run()
