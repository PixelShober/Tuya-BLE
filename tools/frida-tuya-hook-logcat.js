// Crypto logger that writes to Android logcat (tag FRIDAX), so the capture
// survives the frida host connection dropping. Load eternalized; dump with
//   adb logcat -d -s FRIDAX:* > crypto.log
// Only small AES ops are logged (BLE frames are tiny) to keep the ring buffer
// from overflowing with multi-KB cloud blobs.

var TAG = "FRIDAX";
var Log = null;

function out(line) {
  if (Log === null) Log = Java.use("android.util.Log");
  // logcat truncates ~4000 chars; BLE data is far smaller.
  Log.i(TAG, line);
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

// Stack traces are expensive (a new Exception per crypto call bogs the app
// down and gets it watchdog-killed). Off by default; the key+iv+in+out is
// what we need. Flip to true only for a short, targeted run.
var WANT_STACK = false;
function shortStack() {
  if (!WANT_STACK) return "";
  var e = Java.use("java.lang.Exception").$new();
  var trace = e.getStackTrace();
  var s = [];
  for (var i = 2; i < trace.length && s.length < 4; i++) {
    var f = trace[i].toString();
    if (f.indexOf("frida") === -1) s.push(f);
  }
  return " @ " + s.join(" | ");
}

Java.perform(function () {
  var SKS = Java.use("javax.crypto.spec.SecretKeySpec");
  SKS.$init.overload("[B", "java.lang.String").implementation = function (key, alg) {
    out("[KEY] alg=" + alg + " key=" + hex(key));
    return this.$init(key, alg);
  };

  var IPS = Java.use("javax.crypto.spec.IvParameterSpec");
  IPS.$init.overload("[B").implementation = function (iv) {
    out("[IV] " + hex(iv));
    return this.$init(iv);
  };

  var Cipher = Java.use("javax.crypto.Cipher");
  function logAes(algo, input, out_, extra) {
    // Skip large blobs (cloud/API); keep BLE-sized frames.
    if (input !== null && input.length > 256) return;
    out("[AES] " + algo + " in=" + hex(input) + (extra || "") +
        " out=" + hex(out_) + shortStack());
  }
  Cipher.doFinal.overload("[B").implementation = function (input) {
    var r = this.doFinal(input);
    logAes(this.getAlgorithm(), input, r, "");
    return r;
  };
  Cipher.doFinal.overload("[B", "int", "int").implementation = function (input, off, len) {
    var r = this.doFinal(input, off, len);
    if (len <= 256) out("[AES] " + this.getAlgorithm() + " in=" + hex(input) +
        "(off=" + off + " len=" + len + ") out=" + hex(r) + shortStack());
    return r;
  };

  var MD = Java.use("java.security.MessageDigest");
  MD.digest.overload("[B").implementation = function (input) {
    var r = this.digest(input);
    if (input !== null && input.length <= 256)
      out("[HASH] " + this.getAlgorithm() + " in=" + hex(input) + " out=" + hex(r));
    return r;
  };

  var Mac = Java.use("javax.crypto.Mac");
  Mac.doFinal.overload("[B").implementation = function (input) {
    var r = this.doFinal(input);
    if (input !== null && input.length <= 256)
      out("[HMAC] " + this.getAlgorithm() + " in=" + hex(input) + " out=" + hex(r));
    return r;
  };

  out("[*] hooks installed (logcat mode)");
});
