import sys
import traceback

try:
    print("Trying to extract covid19-cough-audio-classification.zip directly...")
    import zipfile
    from pathlib import Path
    
    zf_path = Path(r"c:\Users\maste\Desktop\hacker\backend\data\cough\covid19-cough-audio-classification.zip")
    with zipfile.ZipFile(zf_path, "r") as zf:
        print(f"Zip contains {len(zf.namelist())} files")
        # try to extract one
        zf.extract(zf.namelist()[0], path=zf_path.parent)
        print("Successfully extracted one file")
except Exception as e:
    traceback.print_exc()
