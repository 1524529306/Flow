"""PyInstaller 打包入口：绝对导入，避免相对导入问题。"""
from flowcc.app import main

if __name__ == "__main__":
    raise SystemExit(main())
