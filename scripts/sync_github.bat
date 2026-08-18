@echo off
rem ============================================================
rem FlowCC 3.0.0 GitHub 同步脚本（一次性）
rem 前提：已在 https://github.com/settings/tokens 生成令牌，
rem       或先执行 gh auth login（推荐，浏览器授权一次）。
rem 效果：推送 main、删除旧版本标签、打 v3.0.0、创建 Release。
rem ============================================================
cd /d %~dp0\..

echo [1/4] 推送 main 分支...
git push origin main || goto :err

echo [2/4] 删除 GitHub 上的历史版本标签...
git push origin :refs/tags/v1.5.0 :refs/tags/v2.0.0 :refs/tags/v2.1.0 :refs/tags/v2.2.0 || goto :err

echo [3/4] 推送 v3.0.0 标签...
git push origin v3.0.0 || goto :err

echo [4/4] 创建 GitHub Release 3.0.0（需 gh 已登录）...
gh release create v3.0.0 "release\FlowCC-Setup-3.0.0.exe" ^
  --title "FlowCC 3.0.0" --notes-file docs\release-3.0.0.md || goto :err

echo.
echo 同步完成：main + v3.0.0 + Release 已就绪。
exit /b 0

:err
echo.
echo 同步失败。若为认证问题，请先执行： gh auth login
exit /b 1
