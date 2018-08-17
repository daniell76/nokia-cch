from cch_docx import *

dir = os.path.dirname(__file__)

docx = CCH_HLD_DOCX()

#print(json.dumps(docx.param,indent=4))
#print(json.dumps(docx.contents,indent=4))

#p = docx.document.add_paragraph('This is a test',style=docx.document.styles['Heading 1'])
#print(docx.table)
docx.buildDocFramework()

docx.document.save('demo.docx')

exit()

docx.getTables()
docx.getParagraphs()
docx.getParagraphVars()
docx.applyParams()

# Add document history
docx.addDocHistory()

#for k in docx.paragraphs:
#  p = docx.paragraphs[k]
#  print(p.text)

#for p in docx.document.paragraphs:
#  for r in p.runs:
#    print(r.__dict__)
  
docx.document.save('demo.docx')

exit()

for c in docx.document.sections[0]._sectPr:
  print(ET.dump(c))

print(ET.dump(docx.document.sections[0]._sectPr))
#docbody = docx.document.element.xpath('/w:document/w:body')

# Extract all text
#for b in docbody:
#  b.getroot()
#docx = Document()
#docx.save()

#for p in docx.document.paragraphs:
#  print(p.text)
  
#for t in docx.document.tables:
#  print(t.rows)
 


document.add_heading('Document Title', 0)

p = document.add_paragraph('A plain paragraph having some ')
p.add_run('bold').bold = True
p.add_run(' and some ')
p.add_run('italic.').italic = True

document.add_heading('Heading, level 1', level=1)
document.add_paragraph('Intense quote', style='IntenseQuote')

document.add_paragraph(
    'first item in unordered list', style='ListBullet'
)
document.add_paragraph(
    'first item in ordered list', style='ListNumber'
)

document.add_picture('monty-truth.png', width=Inches(1.25))

table = document.add_table(rows=1, cols=3)
hdr_cells = table.rows[0].cells
hdr_cells[0].text = 'Qty'
hdr_cells[1].text = 'Id'
hdr_cells[2].text = 'Desc'
for item in recordset:
    row_cells = table.add_row().cells
    row_cells[0].text = str(item.qty)
    row_cells[1].text = str(item.id)
    row_cells[2].text = item.desc
