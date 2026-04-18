# linux-ops-center-git AUR Staging Folder

This folder mirrors the package files intended for the AUR repository.

Files to publish:

- `PKGBUILD`
- `.SRCINFO`

Typical workflow:

```bash
git clone ssh://aur@aur.archlinux.org/linux-ops-center-git.git
cd linux-ops-center-git
cp /path/to/your/source/repo/aur/linux-ops-center-git/PKGBUILD .
cp /path/to/your/source/repo/aur/linux-ops-center-git/.SRCINFO .
git add PKGBUILD .SRCINFO
git commit -m "Initial import"
git push
```
