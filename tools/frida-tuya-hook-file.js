// Same crypto logger as frida-tuya-hook.js, but writes to a file inside the
// app so it survives the frida host connection dropping (Wi-Fi loss). Load it
// eternalized; pull the log afterwards from the app's files dir.

var LOGPATH = null;
var WRITER = null;

function ensureWriter() {
  if (WRITER !== null) return WRITER;
  try {
    var ActivityThread = Java.use("android.app.ActivityThread");
    var app = ActivityThread.currentApplication();
    if (app === null) return null;
    var dir = app.getApplicationContext().getFilesDir().getAbsolutePath();
    LOGPATH = dir + "/frida_crypto.log";
    var FW = Java.use("java.io.FileWriter");
    WRITER = FW.$new(LOGPATH, true); // append
    WRITER.write("=== frida crypto log opened ===\n");
    WRITER.flush();
  } catch (e) {
    return null;
  }
  return WRITER;
}

function log(line) {
  var w = ensureWriter();
  if (w === null) return;
  try { w.write(line + "\n"); w.flush(); } catch (e) {}
}

function hex(bytes) {
  if (bytes === null) return "null";
  var b = Java.array('byte', bytes);
  var s = "";
  for (var i = 0; i < b.length; i++) {
    var v = (b[i] < 0 ? b[i] + 256 : b[i]).toString(16);
    s += v.length === 1 ? "0" + v : v;
  }
  return s;
}

function shortStack() {
  var e = Java.use("java.lang.Exception").$new();
  var trace = e.getStackTrace();
  var out = [];
  for (var i = 2; i < trace.length && out.length < 6; i++) {
    var f = trace[i].toString();
    if (f.indexOf("frida") === -1) out.push(f);
  }
  return out.join("\n      ");
}

Java.perform(function () {
  var SKS = Java.use("javax.crypto.spec.SecretKeySpec");
  SKS.$init.overload("[B", "java.lang.String").implementation = function (key, alg) {
    log("\n[KEY ] alg=" + alg + " key=" + hex(key));
    return this.$init(key, alg);
  };

  var IPS = Java.use("javax.crypto.spec.IvParameterSpec");
  IPS.$init.overload("[B").implementation = function (iv) {
    log("[IV  ] " + hex(iv));
    return this.$init(iv);
  };

  var Cipher = Java.use("javax.crypto.Cipher");
  Cipher.doFinal.overload("[B").implementation = function (input) {
    var out = this.doFinal(input);
    log("\n[AES ] " + this.getAlgorithm() +
      "\n  in : " + hex(input) + "\n  out: " + hex(out) +
      "\n  at :\n      " + shortStack());
    return out;
  };
  Cipher.doFinal.overload("[B", "int", "int").implementation = function (input, off, len) {
    var out = this.doFinal(input, off, len);
    log("\n[AES ] " + this.getAlgorithm() +
      "\n  in : " + hex(input) + " (off=" + off + " len=" + len + ")" +
      "\n  out: " + hex(out) + "\n  at :\n      " + shortStack());
    return out;
  };

  var MD = Java.use("java.security.MessageDigest");
  MD.digest.overload("[B").implementation = function (input) {
    var out = this.digest(input);
    log("\n[HASH] " + this.getAlgorithm() + "  in=" + hex(input) + "  out=" + hex(out));
    return out;
  };

  var Mac = Java.use("javax.crypto.Mac");
  Mac.doFinal.overload("[B").implementation = function (input) {
    var out = this.doFinal(input);
    log("\n[HMAC] " + this.getAlgorithm() + "  in=" + hex(input) + "  out=" + hex(out));
    return out;
  };

  log("\n[*] hooks installed (file mode)");
});
