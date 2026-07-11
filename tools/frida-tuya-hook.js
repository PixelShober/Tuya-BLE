// Frida hook for the Smart Life / Tuya app.
// Logs every Java-layer crypto operation (AES, HMAC, MD5/SHA) with key, IV,
// input and output as hex, plus a short stack. Correlate the hex with the
// captured GJ-635 handshake (captures/btfull.log) to recover the session-key
// derivation the lock's pre-handshake uses.
//
// Run:  frida -U -n com.tuya.smartlife -l tools/frida-tuya-hook.js
// (app must be open and next to the lock; then unlock once from the app)

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
  // ponytail: one frame of context is enough to tell which call it was.
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
  // --- Key material: SecretKeySpec captures the raw AES key bytes ---
  var SKS = Java.use("javax.crypto.spec.SecretKeySpec");
  SKS.$init.overload("[B", "java.lang.String").implementation = function (key, alg) {
    console.log("\n[KEY ] SecretKeySpec alg=" + alg + " key=" + hex(key));
    return this.$init(key, alg);
  };

  var IPS = Java.use("javax.crypto.spec.IvParameterSpec");
  IPS.$init.overload("[B").implementation = function (iv) {
    console.log("[IV  ] " + hex(iv));
    return this.$init(iv);
  };

  // --- Cipher: init logs mode+key+iv, doFinal logs in->out ---
  var Cipher = Java.use("javax.crypto.Cipher");
  Cipher.doFinal.overload("[B").implementation = function (input) {
    var out = this.doFinal(input);
    console.log("\n[AES ] " + this.getAlgorithm() +
      "\n  in : " + hex(input) +
      "\n  out: " + hex(out) +
      "\n  at :\n      " + shortStack());
    return out;
  };
  Cipher.doFinal.overload("[B", "int", "int").implementation = function (input, off, len) {
    var out = this.doFinal(input, off, len);
    console.log("\n[AES ] " + this.getAlgorithm() +
      "\n  in : " + hex(input) + " (off=" + off + " len=" + len + ")" +
      "\n  out: " + hex(out) +
      "\n  at :\n      " + shortStack());
    return out;
  };

  // --- Digests (MD5/SHA) — the login_key is md5(local_key[:6]) upstream ---
  var MD = Java.use("java.security.MessageDigest");
  MD.digest.overload("[B").implementation = function (input) {
    var out = this.digest(input);
    console.log("\n[HASH] " + this.getAlgorithm() +
      "  in=" + hex(input) + "  out=" + hex(out));
    return out;
  };

  // --- HMAC ---
  var Mac = Java.use("javax.crypto.Mac");
  Mac.doFinal.overload("[B").implementation = function (input) {
    var out = this.doFinal(input);
    console.log("\n[HMAC] " + this.getAlgorithm() +
      "  in=" + hex(input) + "  out=" + hex(out));
    return out;
  };

  console.log("[*] Tuya crypto hooks installed. Now unlock the lock from the app.");
});
