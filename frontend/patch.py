import os, glob  
files = glob.glob(r"c:\Users\maste\Desktop\hacker\frontend\src\pages\*.jsx") + glob.glob(r"c:\Users\maste\Desktop\hacker\frontend\src\hooks\*.js")  
for fpath in files:  
    with open(fpath, "r", encoding="utf-8") as f: content = f.read()  
    content = content.replace("const q = query(", "if (!db) { if (typeof setLoading === \"function\") setLoading(false); return; }\n    const q = query(")  
    content = content.replace("const snap = await getDoc(doc(db", "if (!db) return;\n        const snap = await getDoc(doc(db")  
    content = content.replace("const fileRef2 = ref(storage", "if (!storage) return;\n      const fileRef2 = ref(storage")  
    content = content.replace("const fileRef = ref(storage", "if (!storage) return;\n        const fileRef = ref(storage")  
    content = content.replace("await addDoc(collection(db", "if (db) await addDoc(collection(db")  
    content = content.replace("const refA = ref(storage", "if (!storage) return;\n      const refA = ref(storage")  
    with open(fpath, "w", encoding="utf-8") as f: f.write(content)  
