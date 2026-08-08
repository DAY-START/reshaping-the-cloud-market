# -*- coding: utf-8 -*-

# ============================================================================
# RESTRICTED USE -- All rights reserved.
# The data, experimental results, and source code in this repository are
# provided for archival / reproducibility reference only. No part of the
# data, experiments, or code may be used, copied, modified, redistributed,
# or incorporated into other works without the author's explicit written
# permission. See LICENSE and NOTICE.md.
# ============================================================================

"""Remove unreferenced image media from a docx to keep only visible figures."""
import zipfile, os, shutil
from xml.etree import ElementTree as ET

DOC = r"C:\Users\ADMIN\Desktop\重塑云市场_AI算力关注与股价分化_V8_顶刊批注整合版_含图.docx"
TMP = DOC + ".tmp"

REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS  = "http://schemas.openxmlformats.org/package/2006/content-types"
W_NS   = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

with zipfile.ZipFile(DOC, 'r') as zin:
    # Read document.xml and find referenced image rIds
    doc_xml = zin.read("word/document.xml").decode('utf-8')
    # Also headers/footers if present
    refs = set()
    for name in zin.namelist():
        if name.startswith("word/") and ('header' in name or 'footer' in name or name == 'word/document.xml'):
            data = zin.read(name).decode('utf-8')
            import re
            refs.update(re.findall(r'blip[^>]*r:embed="rId(\d+)"', data))
            refs.update(re.findall(r'drawing[^>]*r:id="rId(\d+)"', data))
    refs = {f"rId{i}" for i in refs}

    # Read relationships
    rels_xml = zin.read("word/_rels/document.xml.rels").decode('utf-8')
    rel_root = ET.fromstring(rels_xml)
    rels_to_keep = []
    media_to_keep = set()
    for rel in rel_root:
        rid = rel.get('Id')
        target = rel.get('Target')
        typ = rel.get('Type')
        if rid in refs or 'image' not in typ:
            rels_to_keep.append(rel)
            if 'image' in typ:
                media_to_keep.add(target.replace('media/', ''))
        else:
            print("Removing orphaned rel:", rid, target)

    # Build new rels XML
    new_rels = ET.Element('{'+REL_NS+'}Relationships')
    for rel in rels_to_keep:
        new_rels.append(rel)
    new_rels_bytes = ET.tostring(new_rels, encoding='UTF-8', xml_declaration=True)

    # Read content types to update if needed
    ct_xml = zin.read("[Content_Types].xml").decode('utf-8')

    with zipfile.ZipFile(TMP, 'w', zipfile.ZIP_DEFLATED) as zout:
        for name in zin.namelist():
            if name.startswith("word/media/"):
                fname = os.path.basename(name)
                if fname in media_to_keep:
                    zout.writestr(name, zin.read(name))
                else:
                    print("Removing orphaned media:", name)
            elif name == "word/_rels/document.xml.rels":
                zout.writestr(name, new_rels_bytes)
            else:
                zout.writestr(name, zin.read(name))

shutil.move(TMP, DOC)
print("Cleaned", DOC)
