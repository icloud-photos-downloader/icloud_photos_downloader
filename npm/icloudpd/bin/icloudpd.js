#!/usr/bin/env node
"use strict";
var os = require("os");
var fs = require("fs");
var platformKey = `${process.platform} ${os.arch()} ${os.endianness()}`;
var knownPlatforms = {
    "linux x64 LE": {
        "pkgName": "@icloudpd/linux-x64",
        "subPath": "bin/icloudpd" 
    },
    "linux arm64 LE": {
        "pkgName": "@icloudpd/linux-arm64",
        "subPath": "bin/icloudpd" 
    },
    "linux arm LE": {
        "pkgName": "@icloudpd/linux-arm",
        "subPath": "bin/icloudpd" 
    },
    "darwin x64 LE": {
        "pkgName": "@icloudpd/darwin-x64",
        "subPath": "bin/icloudpd" 
    },
    "darwin arm64 LE": {
        "pkgName": "@icloudpd/darwin-arm64",
        "subPath": "bin/icloudpd" 
    },
    "win32 x64 LE": {
        "pkgName": "@icloudpd/win32-x64",
        "subPath": "bin/icloudpd.exe" 
    }
};
if (platformKey in knownPlatforms) {
    var { pkgName, subPath } = knownPlatforms[platformKey];
    var binPath = require.resolve(`${pkgName}/${subPath}`);
    fs.chmodSync(binPath, 493);
    require("child_process").execFileSync(binPath, process.argv.slice(2), { stdio: "inherit" });
} else {
    throw new Error(`Unsupported platform: '${platformKey}'`);
}