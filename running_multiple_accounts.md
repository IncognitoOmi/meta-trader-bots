
### 🛠️ 3rd Account (Funding Pips) Setup Steps:

1.  **Naya Folder Banao:**
    * `C:\Program Files\` mein ja aur firse original MT5 folder ko **Copy-Paste** kar.
    * Naye folder ka naam rakh de: `MetaTrader 5 - FundingPips`.

2.  **Portable Shortcut #2 Banao:**
    * Us naye folder ke andar `terminal64.exe` par right-click kar ke **Shortcut** bana aur use Desktop par le aa.
    * Shortcut ka naam rakh: `MT5 - FundingPips`.
    * Wahi purana step: Properties ➡️ Target ke end mein ek space dekar likh de `/portable`.
    * Target aisa dikhega: `..."MetaTrader 5 - FundingPips\terminal64.exe" /portable`

3.  **Python Script #3 (VS Code Window 3):**
    * Ab teesri Python script bana Funding Pips ke liye. Usme `path` teesre folder ka hoga.

---

### 📂 Tera Final "Triple Account" Structure:

Ab tere computer mein 3 terminals aise chalenge:

| Account | Terminal Folder Path | Python `mt5.initialize(path=...)` |
| :--- | :--- | :--- |
| **The 5%ers** | `C:/Program Files/MetaTrader 5/` | Original Path (Normal) |
| **Blue Guardian**| `C:/Program Files/MetaTrader 5 - BlueGuardian/` | BlueGuardian Folder Path |
| **Funding Pips** | `C:/Program Files/MetaTrader 5 - FundingPips/` | FundingPips Folder Path |

---

### 🧠 Master Rule Yaad Rakhna:

* **Manual Opening:** Pehle teeno terminals ko unke respective shortcuts se manually khol le. (Taaki tu dekh sake ki teeno alag-alag windows mein login hain).
* **VS Code Terminal:** VS Code mein **3 alag-alag terminals** (PowerShell windows) khol aur teeno scripts ko alag-alag run kar.
* **Path is King:** Agar tune teesri script mein path update nahi kiya, toh wo firse kisi purane terminal ko hi "hijack" kar lega aur disconnect wala lafda shuru ho jayega.

**In Short:** Tu jitne chahe utne accounts add kar sakta hai, bas har baar ek naya folder copy kar aur uska alag path use kar. 
