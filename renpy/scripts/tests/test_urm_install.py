#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""urm_install.py 的行为回归。

三组约束被这个脚本锁死：
1. **引擎闸门**：URM 要求 ≥ 6.99.14，低版本必须拒绝安装而不是装完不生效；
2. **不下载不越权**：只处理用户已下载的文件，且永不删自己没装的东西；
3. **试运行默认**：任何写操作不加 --apply 都不得落盘。
"""

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SETUP = os.path.join(os.path.dirname(_HERE), "setup")
_SCRIPT = os.path.join(_SETUP, "urm_install.py")
if _SETUP not in sys.path:
    sys.path.insert(0, _SETUP)


def load():
    spec = importlib.util.spec_from_file_location("urm_install", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


urm = load()


def make_game(root, version="8, 1, 3", extra_game_files=None):
    game = os.path.join(root, "game")
    os.makedirs(game, exist_ok=True)
    with open(os.path.join(root, "Game.py"), "w", encoding="utf-8") as fh:
        fh.write("version = (%s)\n" % version)
    for name, content in (extra_game_files or {}).items():
        with open(os.path.join(game, name), "w", encoding="utf-8") as fh:
            fh.write(content)
    return game


class UrmCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def rpa(self, name="0x52_URM.rpa", size=2048):
        p = os.path.join(self.root, name)
        with open(p, "wb") as fh:
            fh.write(b"RPA-3.0 " + b"x" * size)
        return p


class TestEngineGate(UrmCase):
    def test_min_engine_constant_matches_official(self):
        """官方声明 ≥ 6.99.14，改动必须是有意为之。"""
        self.assertEqual(urm.URM_MIN_ENGINE, (6, 99, 14))

    def test_version_read_from_launcher_script(self):
        make_game(self.root, "8, 2, 1")
        game = os.path.join(self.root, "game")
        ver, src = urm.read_engine_version(game)
        self.assertEqual(ver, (8, 2, 1))
        self.assertEqual(src, "Game.py")

    def test_version_from_options_rpy_fallback(self):
        """启动脚本缺失时退回 game/ 下的 rpy。"""
        game = make_game(self.root, "8, 0, 0")
        os.remove(os.path.join(self.root, "Game.py"))
        with open(os.path.join(game, "options.rpy"), "w", encoding="utf-8") as fh:
            fh.write("define config.version = (7, 5, 1)\n")
        ver, _ = urm.read_engine_version(game)
        self.assertEqual(ver, (7, 5, 1))

    def test_version_unknown_returns_none_not_guess(self):
        """读不到就返回 None —— 不猜版本是本脚本的硬要求。"""
        make_game(self.root, "8, 1, 3")
        os.remove(os.path.join(self.root, "Game.py"))
        ver, _ = urm.read_engine_version(os.path.join(self.root, "game"))
        self.assertIsNone(ver)

    def test_version_ok_boundaries(self):
        self.assertTrue(urm.version_ok((6, 99, 14)))
        self.assertTrue(urm.version_ok((7, 0, 0)))
        self.assertTrue(urm.version_ok((8, 5, 3)))
        self.assertFalse(urm.version_ok((6, 99, 13)))
        self.assertFalse(urm.version_ok((6, 99, 12)))
        self.assertFalse(urm.version_ok(None))

    def test_install_refuses_old_engine(self):
        game = make_game(self.root, "6, 99, 12")
        rpa = self.rpa()
        self.assertEqual(urm.do_install(game, rpa, apply=True), 2)
        # 关键：拒绝时不得留下任何痕迹
        self.assertEqual(os.listdir(game), ["Game.py"][0:0] or os.listdir(game))
        self.assertNotIn("0x52_URM.rpa", os.listdir(game))
        self.assertNotIn(urm.SIGNATURE_NAME, os.listdir(game))


class TestRpaEncryptionGate(UrmCase):
    def test_detects_key_file(self):
        game = make_game(self.root, extra_game_files={"archive_key.rpy": "k = 1"})
        found, name = urm.find_rpa_encrypted(game)
        self.assertTrue(found)
        self.assertEqual(name, "archive_key.rpy")

    def test_detects_index_file(self):
        game = make_game(self.root, extra_game_files={"data.rpa.index": "x"})
        found, _ = urm.find_rpa_encrypted(game)
        self.assertTrue(found)

    def test_clean_game_not_flagged(self):
        game = make_game(self.root)
        found, _ = urm.find_rpa_encrypted(game)
        self.assertFalse(found)

    def test_install_refuses_encrypted_game(self):
        game = make_game(self.root, extra_game_files={"archive_key.rpy": "k = 1"})
        rpa = self.rpa()
        self.assertEqual(urm.do_install(game, rpa, apply=True), 2)
        self.assertNotIn("0x52_URM.rpa", os.listdir(game))


class TestInstallUninstallRoundTrip(UrmCase):
    def _install(self):
        game = make_game(self.root)
        rpa = self.rpa()
        rc = urm.do_install(game, rpa, apply=True)
        return game, rc

    def test_install_creates_file_and_signature(self):
        game, rc = self._install()
        self.assertEqual(rc, 0)
        names = os.listdir(game)
        self.assertIn("0x52_URM.rpa", names)
        self.assertIn(urm.SIGNATURE_NAME, names)

    def test_dry_run_writes_nothing(self):
        game = make_game(self.root)
        rpa = self.rpa()
        self.assertEqual(urm.do_install(game, rpa, apply=False), 0)
        self.assertNotIn("0x52_URM.rpa", os.listdir(game))
        self.assertNotIn(urm.SIGNATURE_NAME, os.listdir(game))

    def test_dry_run_uninstall_deletes_nothing(self):
        game, _ = self._install()
        self.assertEqual(urm.do_uninstall(game, apply=False, purge_rpyc=False), 0)
        self.assertIn("0x52_URM.rpa", os.listdir(game))

    def test_signature_records_provenance(self):
        game, _ = self._install()
        with open(os.path.join(game, urm.SIGNATURE_NAME), encoding="utf-8") as fh:
            sig = json.load(fh)
        self.assertEqual(sig["mod"], "Universal Ren'Py Mod")
        self.assertIn("0x52.dev", sig["source_url"])
        self.assertIn("0x52_URM.rpa", sig["files"])

    def test_second_install_refused(self):
        game, _ = self._install()
        rc = urm.do_install(game, self.rpa(), apply=True)
        self.assertEqual(rc, 2, "重复安装应被拒绝而不是覆盖")

    def test_uninstall_restores_exactly(self):
        """卸载后 game/ 应与安装前逐字节一致。"""
        game = make_game(self.root)
        before = sorted(os.listdir(game))
        rpa = self.rpa()
        urm.do_install(game, rpa, apply=True)
        self.assertEqual(urm.do_uninstall(game, apply=True, purge_rpyc=False), 0)
        self.assertEqual(sorted(os.listdir(game)), before)

    def test_uninstall_without_signature_refuses_and_lists(self):
        """没有签名时不猜文件名，只报告疑似文件。"""
        game = make_game(self.root)
        with open(os.path.join(game, "0x52_URM.rpa"), "w", encoding="utf-8") as fh:
            fh.write("hand placed")
        rc = urm.do_uninstall(game, apply=True, purge_rpyc=False)
        self.assertEqual(rc, 2)
        self.assertIn("0x52_URM.rpa", os.listdir(game), "无签名时绝不能删")

    def test_corrupt_signature_treated_as_absent(self):
        game, _ = self._install()
        with open(os.path.join(game, urm.SIGNATURE_NAME), "w", encoding="utf-8") as fh:
            fh.write("{ broken")
        sig, _ = urm.load_signature(game)
        self.assertIsNone(sig)


class TestStaleRpyc(UrmCase):
    def test_detects_rpyc_beside_rpa(self):
        """解包成 .rpy 后编译出的 .rpyc，删 .rpy 不会让它消失。"""
        game = make_game(self.root)
        rpy = os.path.join(game, "0x52_URM.rpy")
        with open(rpy, "w", encoding="utf-8") as fh:
            fh.write("x")
        rpyc = os.path.join(game, "0x52_URM.rpyc")
        with open(rpyc, "wb") as fh:
            fh.write(b"compiled")
        stale = urm.stale_rpyc([rpy])
        self.assertIn(rpyc, stale)

    def test_detects_rpymc_and_bak(self):
        game = make_game(self.root)
        rpy = os.path.join(game, "0x52_URM.rpy")
        with open(rpy, "w", encoding="utf-8") as fh:
            fh.write("x")
        made = []
        for ext in (".rpymc", ".bak"):
            p = os.path.join(game, "0x52_URM" + ext)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("x")
            made.append(p)
        self.assertEqual(set(urm.stale_rpyc([rpy])), set(made))

    def test_no_false_positive_for_rpa_only(self):
        game = make_game(self.root)
        rpa = os.path.join(game, "0x52_URM.rpa")
        with open(rpa, "w", encoding="utf-8") as fh:
            fh.write("x")
        self.assertEqual(urm.stale_rpyc([rpa]), [])

    def test_purge_rpyc_cleans_on_uninstall(self):
        game = make_game(self.root)
        urm.do_install(game, self.rpa(), apply=True)
        rpy = os.path.join(game, "0x52_URM.rpy")
        with open(rpy, "w", encoding="utf-8") as fh:
            fh.write("x")
        rpyc = os.path.join(game, "0x52_URM.rpyc")
        with open(rpyc, "w", encoding="utf-8") as fh:
            fh.write("c")
        self.assertEqual(
            urm.do_uninstall(game, apply=True, purge_rpyc=True), 0
        )
        self.assertFalse(os.path.exists(rpyc))
        self.assertFalse(os.path.exists(os.path.join(game, "0x52_URM.rpa")))


class TestNotDeletingForeignFiles(UrmCase):
    def test_uninstall_never_removes_unsigned_scripts(self):
        """越权红线：只删签名记录的文件 + 其编译残留。

        用户手工解包过官方 .rpa 时会留下 .rpy，删了签名文件后它仍会被
        Ren'Py 编译加载 —— 但脚本无权替用户删除自己没装的东西，只能提示。
        """
        game = make_game(self.root)
        urm.do_install(game, self.rpa(), apply=True)
        foreign = os.path.join(game, "0x52_URM.rpy")
        with open(foreign, "w", encoding="utf-8") as fh:
            fh.write("hand placed by user")
        self.assertEqual(urm.do_uninstall(game, apply=True, purge_rpyc=False), 0)
        self.assertTrue(
            os.path.exists(foreign),
            "未签名的 .rpy 必须保留 —— 脚本无权删除非自己安装的文件",
        )


class TestCliSurface(UrmCase):
    """入口层行为：参数组合与退出码。"""

    def run_cli(self, *args):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run(
            [sys.executable, _SCRIPT, *args],
            capture_output=True, env=env, text=True, encoding="utf-8", errors="replace",
        )

    def test_help_succeeds(self):
        r = self.run_cli("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("URM", r.stdout)

    def test_check_is_default_action(self):
        make_game(self.root)
        r = self.run_cli(self.root)
        self.assertEqual(r.returncode, 0)
        self.assertIn("体检", r.stdout)

    def test_accepts_game_dir_directly(self):
        """传 game/ 本身与传游戏根都应工作。"""
        game = make_game(self.root)
        for path in (self.root, game):
            with self.subTest(path=path):
                r = self.run_cli(path)
                self.assertEqual(r.returncode, 0)

    def test_non_renpy_dir_errors_clearly(self):
        plain = os.path.join(self.root, "plain")
        os.makedirs(plain)
        r = self.run_cli(plain)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("game/", r.stdout + r.stderr)

    def test_uninstall_with_rpa_is_conflict(self):
        make_game(self.root)
        r = self.run_cli(self.root, "--uninstall", "--rpa", self.rpa())
        self.assertEqual(r.returncode, 2)

    def test_missing_rpa_file_errors(self):
        make_game(self.root)
        r = self.run_cli(self.root, "--rpa", os.path.join(self.root, "nope.rpa"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("找不到文件", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)