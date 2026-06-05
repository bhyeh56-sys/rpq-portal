//+------------------------------------------------------------------+
//| RPQSnapshotSender.mq5                                            |
//| Sends signed MT5 account snapshots to the RPQ webhook.            |
//+------------------------------------------------------------------+
#property strict
#property version "1.00"

input string WebhookUrl = "https://rpqtfund.com/fx/mt5/snapshot";
input long   FxAccountId = 0;
input string FxSecret = "";
input int    SendIntervalSeconds = 300;
input bool   DebugMode = false;

datetime g_last_send = 0;
bool g_hmac_selftest_ok = true;

uint K[64] =
{
   0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
   0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
   0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
   0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
   0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
   0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
   0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
   0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
};

uint RotR(const uint x, const int n)
{
   return (x >> n) | (x << (32 - n));
}

uint Ch(const uint x, const uint y, const uint z)
{
   return (x & y) ^ ((~x) & z);
}

uint Maj(const uint x, const uint y, const uint z)
{
   return (x & y) ^ (x & z) ^ (y & z);
}

uint BigSigma0(const uint x)
{
   return RotR(x, 2) ^ RotR(x, 13) ^ RotR(x, 22);
}

uint BigSigma1(const uint x)
{
   return RotR(x, 6) ^ RotR(x, 11) ^ RotR(x, 25);
}

uint SmallSigma0(const uint x)
{
   return RotR(x, 7) ^ RotR(x, 18) ^ (x >> 3);
}

uint SmallSigma1(const uint x)
{
   return RotR(x, 17) ^ RotR(x, 19) ^ (x >> 10);
}

void StringToUtf8Bytes(const string value, uchar &out[])
{
   char tmp[];
   int len = StringToCharArray(value, tmp, 0, -1, CP_UTF8);
   if(len < 0)
      len = 0;
   if(len > 0 && tmp[len - 1] == 0)
      len--;

   ArrayResize(out, len);
   for(int i = 0; i < len; i++)
      out[i] = (uchar)tmp[i];
}

void UcharBytesToCharBytes(const uchar &src[], char &dst[])
{
   int len = ArraySize(src);
   ArrayResize(dst, len);
   for(int i = 0; i < len; i++)
      dst[i] = (char)src[i];
}

void Sha256(const uchar &data[], uchar &digest[])
{
   int len = ArraySize(data);
   int padded_len = len + 1 + 8;
   int rem = padded_len % 64;
   if(rem != 0)
      padded_len += 64 - rem;

   uchar msg[];
   ArrayResize(msg, padded_len);
   ArrayInitialize(msg, 0);
   for(int i = 0; i < len; i++)
      msg[i] = data[i];
   msg[len] = 0x80;

   ulong bit_len = (ulong)len * 8;
   for(int i = 0; i < 8; i++)
      msg[padded_len - 1 - i] = (uchar)((bit_len >> (8 * i)) & 0xff);

   uint h0 = 0x6a09e667;
   uint h1 = 0xbb67ae85;
   uint h2 = 0x3c6ef372;
   uint h3 = 0xa54ff53a;
   uint h4 = 0x510e527f;
   uint h5 = 0x9b05688c;
   uint h6 = 0x1f83d9ab;
   uint h7 = 0x5be0cd19;

   for(int offset = 0; offset < padded_len; offset += 64)
   {
      uint w[64];
      for(int i = 0; i < 16; i++)
      {
         int j = offset + i * 4;
         w[i] = ((uint)msg[j] << 24) | ((uint)msg[j + 1] << 16) | ((uint)msg[j + 2] << 8) | (uint)msg[j + 3];
      }
      for(int i = 16; i < 64; i++)
         w[i] = SmallSigma1(w[i - 2]) + w[i - 7] + SmallSigma0(w[i - 15]) + w[i - 16];

      uint a = h0;
      uint b = h1;
      uint c = h2;
      uint d = h3;
      uint e = h4;
      uint f = h5;
      uint g = h6;
      uint h = h7;

      for(int i = 0; i < 64; i++)
      {
         uint t1 = h + BigSigma1(e) + Ch(e, f, g) + K[i] + w[i];
         uint t2 = BigSigma0(a) + Maj(a, b, c);
         h = g;
         g = f;
         f = e;
         e = d + t1;
         d = c;
         c = b;
         b = a;
         a = t1 + t2;
      }

      h0 += a;
      h1 += b;
      h2 += c;
      h3 += d;
      h4 += e;
      h5 += f;
      h6 += g;
      h7 += h;
   }

   uint hs[8] = {h0, h1, h2, h3, h4, h5, h6, h7};
   ArrayResize(digest, 32);
   for(int i = 0; i < 8; i++)
   {
      digest[i * 4] = (uchar)((hs[i] >> 24) & 0xff);
      digest[i * 4 + 1] = (uchar)((hs[i] >> 16) & 0xff);
      digest[i * 4 + 2] = (uchar)((hs[i] >> 8) & 0xff);
      digest[i * 4 + 3] = (uchar)(hs[i] & 0xff);
   }
}

void HmacSha256(const uchar &key[], const uchar &body[], uchar &digest[])
{
   uchar key_block[];
   ArrayResize(key_block, 64);
   ArrayInitialize(key_block, 0);

   if(ArraySize(key) > 64)
   {
      uchar key_hash[];
      Sha256(key, key_hash);
      for(int i = 0; i < 32; i++)
         key_block[i] = key_hash[i];
   }
   else
   {
      for(int i = 0; i < ArraySize(key); i++)
         key_block[i] = key[i];
   }

   uchar inner[];
   uchar outer[];
   int body_len = ArraySize(body);
   ArrayResize(inner, 64 + body_len);
   ArrayResize(outer, 64 + 32);

   for(int i = 0; i < 64; i++)
   {
      inner[i] = (uchar)(key_block[i] ^ 0x36);
      outer[i] = (uchar)(key_block[i] ^ 0x5c);
   }
   for(int i = 0; i < body_len; i++)
      inner[64 + i] = body[i];

   uchar inner_hash[];
   Sha256(inner, inner_hash);
   for(int i = 0; i < 32; i++)
      outer[64 + i] = inner_hash[i];

   Sha256(outer, digest);
}

string BytesToHex(const uchar &data[])
{
   string hex = "0123456789abcdef";
   string out = "";
   for(int i = 0; i < ArraySize(data); i++)
   {
      int high = (data[i] >> 4) & 0x0f;
      int low = data[i] & 0x0f;
      out += StringSubstr(hex, high, 1) + StringSubstr(hex, low, 1);
   }
   return out;
}

bool IsLowercaseHex64(const string value)
{
   if(StringLen(value) != 64)
      return false;

   for(int i = 0; i < 64; i++)
   {
      ushort ch = StringGetCharacter(value, i);
      bool is_digit = (ch >= '0' && ch <= '9');
      bool is_lower_hex = (ch >= 'a' && ch <= 'f');
      if(!is_digit && !is_lower_hex)
         return false;
   }
   return true;
}

bool HmacSelfTest()
{
   uchar key_bytes[];
   uchar body_bytes[];
   uchar sig_bytes[];
   StringToUtf8Bytes("key", key_bytes);
   StringToUtf8Bytes("The quick brown fox jumps over the lazy dog", body_bytes);
   HmacSha256(key_bytes, body_bytes, sig_bytes);

   string actual = BytesToHex(sig_bytes);
   string expected = "f7bc83f430538424b13298e6aa6fb143ef4d59a14946175997479dbc2d1a3cd8";
   return (actual == expected && IsLowercaseHex64(actual));
}

string IsoTimeUtc()
{
   MqlDateTime dt;
   TimeToStruct(TimeGMT(), dt);
   return StringFormat("%04d-%02d-%02dT%02d:%02d:%02d+00:00",
                       dt.year, dt.mon, dt.day, dt.hour, dt.min, dt.sec);
}

string MoneyValue(const double value)
{
   return DoubleToString(value, 2);
}

string BuildPayload()
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double margin = AccountInfoDouble(ACCOUNT_MARGIN);
   double free_margin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);

   return StringFormat("{\"asof_at\":\"%s\",\"balance\":\"%s\",\"equity\":\"%s\",\"free_margin\":\"%s\",\"margin\":\"%s\"}",
                       IsoTimeUtc(),
                       MoneyValue(balance),
                       MoneyValue(equity),
                       MoneyValue(free_margin),
                       MoneyValue(margin));
}

bool SendSnapshot()
{
   if(!g_hmac_selftest_ok)
   {
      Print("HMAC self-test failed; snapshot send skipped.");
      return false;
   }

   if(FxAccountId <= 0)
   {
      Print("RPQ snapshot send skipped: FxAccountId must be set.");
      return false;
   }
   if(FxSecret == "")
   {
      Print("RPQ snapshot send skipped: FxSecret is empty.");
      return false;
   }

   string body = BuildPayload();
   uchar body_bytes[];
   uchar secret_bytes[];
   StringToUtf8Bytes(body, body_bytes);
   StringToUtf8Bytes(FxSecret, secret_bytes);

   uchar sig_bytes[];
   HmacSha256(secret_bytes, body_bytes, sig_bytes);
   string signature = BytesToHex(sig_bytes);

   if(!IsLowercaseHex64(signature))
   {
      PrintFormat("RPQ snapshot signing failed: signature_len=%d signature_is_lowercase_hex=false", StringLen(signature));
      return false;
   }

   uchar body_hash[];
   Sha256(body_bytes, body_hash);
   if(DebugMode)
   {
      PrintFormat("RPQ debug: body_len=%d body_sha256=%s signature_len=%d signature_is_lowercase_hex=true",
                  ArraySize(body_bytes), BytesToHex(body_hash), StringLen(signature));
   }

   char post[];
   UcharBytesToCharBytes(body_bytes, post);

   char result[];
   string result_headers = "";
   string headers = "Content-Type: application/json\r\n"
                    "X-FX-Account-Id: " + IntegerToString(FxAccountId) + "\r\n"
                    "X-Signature: " + signature + "\r\n";

   ResetLastError();
   int status = WebRequest("POST", WebhookUrl, headers, 20000, post, result, result_headers);
   int err = GetLastError();
   string response = CharArrayToString(result, 0, -1, CP_UTF8);

   if(status == -1)
   {
      PrintFormat("RPQ snapshot WebRequest failed: status=-1 error=%d response=%s", err, response);
      return false;
   }

   if(status < 200 || status >= 300)
   {
      PrintFormat("RPQ snapshot rejected: status=%d error=%d response=%s", status, err, response);
      return false;
   }

   PrintFormat("RPQ snapshot sent: status=%d response=%s", status, response);
   return true;
}

int OnInit()
{
   int interval = SendIntervalSeconds;
   if(interval < 1)
      interval = 1;
   EventSetTimer(interval);
   PrintFormat("RPQSnapshotSender started. interval=%d seconds url=%s fx_account_id=%s",
               interval, WebhookUrl, IntegerToString(FxAccountId));

   if(DebugMode)
   {
      g_hmac_selftest_ok = HmacSelfTest();
      PrintFormat("RPQ debug: hmac_selftest=%s", g_hmac_selftest_ok ? "true" : "false");
      if(!g_hmac_selftest_ok)
      {
         Print("HMAC self-test failed; snapshot send disabled.");
         return INIT_SUCCEEDED;
      }
   }

   if(SendSnapshot())
      g_last_send = TimeCurrent();
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   PrintFormat("RPQSnapshotSender stopped. reason=%d", reason);
}

void OnTimer()
{
   datetime now = TimeCurrent();
   int interval = SendIntervalSeconds;
   if(interval < 1)
      interval = 1;

   if(g_last_send != 0 && (now - g_last_send) < interval)
      return;

   if(SendSnapshot())
      g_last_send = now;
}
