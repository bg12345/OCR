import pytesseract,re,pdf2image,os,sys,cv2
from flask import request, jsonify
from PDFTextExtract import get_pdf_images
from PIL import Image
from io import BytesIO
from flask_cors import cross_origin
from preprocessing import get_preprocessed_file, detection
from datetime import date
from pyaadhaar.decode import AadhaarSecureQr,AadhaarOldQr
from collections import OrderedDict
from app import app


suffixes = ("pdf", "jpeg", "png", "jpg")
address=os.getcwd()+"/doc_files/"
pytesseract.pytesseract.tesseract_cmd=r"C:\Program Files\Tesseract-OCR\tesseract.exe"
poppler_path = r"C:\Users\Sameer.DESKTOP-E7MGQPO\Downloads\Release-21.09.0-1\poppler-21.09.0\Library\bin"
url="http://127.0.0.1:5000/doc_files/{}/"

@app.route("/")
@cross_origin()
def index():
    return "API Documentation",201


@app.route("/pan_ocr",methods=["POST"])
@cross_origin()
def pan_ocr():
    if request.method=="POST":
        file=request.files["file"]
        suffix = file.filename.split(".")[1].lower()
        temp_path = os.path.join(address + "pan/", "temp."+suffix)
        file.save(temp_path)
        keywords="INCOME TAX DEPARTMENT GOVT. INDIA".split()
        if suffix in suffixes:
            if suffix == "pdf":
                imgs = get_pdf_images(file)
                if len(imgs)==1:
                   (mode, size, data) = imgs[0]
                   file = BytesIO(data)
            else:
                   file=None
            file = get_preprocessed_file(path=temp_path, file=file)
            txt = pytesseract.image_to_string(file, lang="eng+hin")
            names = list(filter(lambda x:len(x)>2 and not any(i in x for i in keywords),re.findall(r"\b[A-Z\.]+(?:[ \r\t\f]+[A-Z\.]+)*\b", txt)))
            if len(names)>1:
                customer_name=names[0]
                father_name=names[1]
                pan_type="Individual"
                if re.search(customer_name,txt).end()+1==re.search(father_name,txt).start():
                    customer_name+=" "+father_name
                    try:
                        father_name=names[2]
                    except:
                        father_name=None
                        pan_type="Business"
            else:
                customer_name=names[0]
                father_name=None
                pan_type="Business"
            try:
                pan_no = re.search(r"[A-Z]{5}[0-9oO]{4}[A-Z]", txt,flags=re.IGNORECASE).group(0).upper()
                num = re.search(r"[0-9oO]{4}", pan_no).group(0)
                if "o" in num or "O" in num:
                    pan_no = pan_no.replace(num, num.replace("o", "0").replace("O", "0"))
            except:
                pan_no = None
            try:
                dob = re.search(r"(\d+/\d+/\d+)", txt).group(0)
            except:
                dob = None
            filename = customer_name.split()[0]+"_"+pan_no+ "." + suffix
            path = os.path.join(address + "pan/", filename)
            if not os.path.exists(path) and os.path.exists(temp_path):
                os.rename(temp_path,path)
            data={"name":customer_name,"father_name":father_name,"pan_number":pan_no,
                  "pan_type":pan_type,"date_of_birth_or_registration":dob,"page_count":1,
                  "file_path":url.format("pan")+filename,"file_type":suffix}
            return jsonify(data)
        return "Please submit valid file", 201

@app.route("/dl_ocr",methods=["POST"])
@cross_origin()
def dl_ocr():
    if request.method=="POST":
        file = request.files["file"]
        suffix = file.filename.split(".")[1].lower()
        temp_path = os.path.join(address + "dl/", "temp." + suffix)
        file.save(temp_path)
        keywords = "NCT DOB".split()
        if suffix in suffixes:
            if suffix == "pdf":
                imgs = get_pdf_images(file)
                if len(imgs)==1:
                    (mode, size, data) = imgs[0]
                    file = BytesIO(data)
            else:
                file=None
            file = get_preprocessed_file(path=temp_path, file=file)
            txt = pytesseract.image_to_string(file)
            names = list(filter(lambda x:len(x)>2 and not any(i in x for i in keywords),re.findall(r"\b[A-Z\.]+(?:[ \r\t\f]+[A-Z\.]+)*\b", txt)))
            customer_name=names[0]
            father_name=names[1]
            try:
                dl_no = re.search(r"[A-Z]{2}[-]?[0-9oO]{2}[\s]?[0-9oO]{11}", txt,flags=re.IGNORECASE).group(0).upper()
                num = re.search(r"[0-9oO]{2}[\s]?[0-9oO]{11}", dl_no).group(0)
                if "o" in num or "O" in num:
                    dl_no = dl_no.replace(num, num.replace("o", "0").replace("O", "0"))
            except:
                dl_no = None
            issue_date = None
            try:
                dates = [j for i in re.findall(r"(\d+/\d+/\d+)|(\d+-\d+-\d+)", txt) for j in i if j != ""]
                dates = [i for i in dates if dates.count(i) == 1]
                dates = {i: date.today().year - int(re.split(r"[-/]", i)[-1]) for i in dates}
                dob = max(dates, key=dates.get).replace("-", "/")
                validity = min(dates, key=dates.get).replace("-", "/")
                for i in dates:
                    if i != dob and i != validity:
                        issue_date = i.replace("-", "/")
                        break
            except:
                dob = None
                validity = None
            try:
                bg = re.sub(r"(Blood Group|B[.]?G[.]?)[\s]?[:.]?[\s]", "",re.search(r"(Blood Group|B[.]?G[.]?)[\s]?[:.]?[\s](\w+)", txt, flags=re.IGNORECASE).group(0),flags=re.IGNORECASE)
                if len(bg) > 3:
                    bg = "U"
            except:
                bg = None
            try:
                dl_address = re.split(r"(Address|ress)[\s]?[:.]?[\s]", txt, flags=re.IGNORECASE)[2].split("\n\n")[0].replace("\n", " ")
            except:
                dl_address = None
            filename = customer_name.split()[0] + "_" + re.sub(r"[\s-]","",dl_no) + "." + suffix
            path = os.path.join(address + "dl/", filename)
            if not os.path.exists(path) and os.path.exists(temp_path):
                os.rename(temp_path, path)
            data = {
                "name": customer_name,
                "dl_number": dl_no,
                "date_of_birth": dob,
                "issue_date": issue_date,
                "validity": validity,
                "address": dl_address,
                "sdw": father_name,
                "blood_group": bg,
                "page_count": 1,
                "file_type": suffix,
                "file_path": url.format("dl") + filename
            }
            return jsonify(data)
        return "Please submit valid file", 201


@app.route("/aadhaar_ocr",methods=["POST"])
@cross_origin()
def aadhaar_ocr():
    if request.method=="POST":
        front_file=request.files["front_file"]
        back_file=request.files.get("back_file",None)
        front_suffix = front_file.filename.split(".")[1].lower()
        front_temp_path = os.path.join(address + "aadhaar/", "front_temp." + front_suffix)
        front_file.save(front_temp_path)
        if back_file:
            back_suffix = back_file.filename.split(".")[1].lower()
            back_temp_path = os.path.join(address + "aadhaar/", "back_temp." + back_suffix)
            back_file.save(back_temp_path)
        else:
            back_suffix,back_temp_path=None,None
        if front_suffix in suffixes or back_suffix in suffixes:
            if back_file is None and front_suffix == "pdf":
                front_bytesio_path = os.path.join(address + "aadhaar/", "front_bytesio.jpeg")
                back_bytesio_path = os.path.join(address + "aadhaar/", "back_bytesio.jpeg")
                try:
                    try:
                        imgs = get_pdf_images(front_file)
                        (mode, size, data) = imgs[0]
                        front_file = BytesIO(data)
                        img=Image.open(front_file)
                        img.save(front_bytesio_path)
                        if len(imgs) == 2:
                            (mode, size, data) = imgs[1]
                            back_file = BytesIO(data)
                            img = Image.open(back_file)
                            img.save(back_bytesio_path)
                    except:
                          img = pdf2image.convert_from_path(pdf_path=front_temp_path,poppler_path=poppler_path)
                          img[0].save(front_bytesio_path)
                          if len(img)==2:
                              img[1].save(back_bytesio_path)
                except:
                    if os.path.exists(front_temp_path):
                        os.remove(front_temp_path)
                    if back_temp_path:
                        if os.path.exists(back_temp_path):
                            os.remove(back_temp_path)
                    return "PDF is password protected", 201
            else:
               front_bytesio_path,back_bytesio_path=None,None
            front_qr_code=detection(front_bytesio_path) if front_bytesio_path else detection(front_temp_path)
            img = cv2.imread(front_bytesio_path) if front_bytesio_path else cv2.imread(front_temp_path)
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            front_d = pytesseract.image_to_data(rgb, output_type=pytesseract.Output.DICT, lang="eng+hin")
            txt=None
            if front_bytesio_path:
                if os.path.exists(front_bytesio_path):
                    txt=pytesseract.image_to_string(Image.open(front_bytesio_path), lang="eng+hin")
                    os.remove(front_bytesio_path)
            if front_qr_code:
               qr_data=front_qr_code.data.decode()
               if qr_data.isdigit():
                   d=AadhaarSecureQr(int(qr_data)).decodeddata()
               else:
                  d=AadhaarOldQr(qr_data).decodeddata()
               if d.get("uid",None):
                   aadhaar_number=" ".join(d["uid"][i:i + 4] for i in range(0, len(d["uid"]), 4))
                   fh = re.sub(r"[SWD]/O: ", "", d["co"])
                   aadhaar_address=", ".join(d.get(i, "") for i in ("house", "street", "loc", "vtc", "dist", "po", "state", "pc")).replace(", ,",",")
               else:
                   no=re.search(r"[0-9oO]{4} [0-9oO]{4} [0-9oO]{4}", txt).group(0)
                   aadhaar_number=no if d["adhaar_last_4_digit"] in no else None
                   fh=re.sub(r"[SWD]/O: ", "", d["careof"])
                   aadhaar_address=", ".join(d.get(i,"") for i in ("house","street","location","vtc","district","postoffice","state","pincode")).replace(", ,",",")
               front_filename = "Front_"+d["name"].split()[0] + "_" + aadhaar_number.replace(" ","") + "." + front_suffix
               front_path = os.path.join(address + "aadhaar/", front_filename)
               if not os.path.exists(front_path) and os.path.exists(front_temp_path):
                   os.rename(front_temp_path, front_path)
               if back_file:
                   back_filename = "Back_" + d["name"].split()[0] + "_" + aadhaar_number.replace(" ","") + "." + back_suffix
                   back_path = os.path.join(address + "aadhaar/", back_filename)
                   if not os.path.exists(back_path) and os.path.exists(back_temp_path):
                       os.rename(back_temp_path, back_path)
               data = {"name": d["name"], "aadhaar_number":aadhaar_number,
                       "gender": "Male" if d["gender"] == "M" else "Female" if d["gender"] == "F" else "Transgender",
                       "father_or_husband_name": fh,
                       "date_or_year_of_birth": d["dob"].replace("-","/") if d.get("dob", None) else d["yob"],
                       "address": aadhaar_address,
                       "page_count":2 if back_file else 1, "front_file_type":front_suffix, "back_file_type":back_suffix,
                       "front_file_path":url.format("aadhaar")+front_filename,
                       "back_file_path":url.format("aadhaar")+back_filename if back_file else None}
               return jsonify(data)
            keywords = ["", "/", "-", "Government", "ofIndia", "of India", "of", "India", "Unique", "Identification",
                        "Authority", "Aadhaar", "No", "No.", "To", "No.:", "To,", "AN.",
                        "help@uidai.gov.in", "www.uidai.gov.in", "D/O", "D/O:", "Ref:", "Ref", "S/O:",
                        "S/O", "VTC:", "VTC","W/O:","W/O",
                        "PO:", "PO", "Sub", "District", "District:", "State:", "PIN", "Code:", "Code","Your"]
            data={"front_file_type":front_suffix,"back_file_type":None,"page_count":1,"back_file_path":None,
                  "father_or_husband_name":None,"address":None,"gender":None,"date_or_year_of_birth":None}
            count, dob, an, ad = 0, 0, 0, 0
            flag=False
            try:
                for i in range(0, len(front_d["text"])):
                    text = front_d["text"][i]
                    conf = int(float(front_d["conf"][i]))
                    if text not in keywords and conf > 80 and re.match(r'[a-zA-Z-0-9]', text) and len(text)>=2:
                        if count == 0:
                            if re.match(r"\d{4}/\d{5}/\d{5}", text) or text=="Enrollment":
                                flag=True
                                continue
                            data["name"] = text
                        elif count == 1:
                            data["name"] += " " + text.replace(",", "")
                        if flag:
                            if count == 2:
                                data["father_or_husband_name"] = text
                            elif count == 3:
                                data["father_or_husband_name"] += " " + text.replace(",", "")
                            elif count > 3:
                                if ad == 0:
                                    data["address"] = text
                                else:
                                    if not re.match(r"Mobile:|Mobile|\d{9,10}",text):
                                        data["address"] += " " + text
                                    else:
                                        flag=False
                                ad += 1
                        if re.match(r'\d{2}/\d{2}/\d{4}', text) and dob == 0:
                            if date.today().year-int(text.split("/")[-1])>=18:
                                data["date_or_year_of_birth"] = text
                                dob += 1
                        elif re.match(r'MALE|FEMALE|TRANSGENDER', text, flags=re.IGNORECASE):
                            data["gender"] = text
                        elif re.match(r'^\d{4}$', text):
                            if an == 0:
                                data["aadhaar_number"] = text
                            else:
                                data["aadhaar_number"] += " " + text
                            an += 1
                        count += 1
                if back_temp_path or back_bytesio_path:
                    if os.path.exists(back_temp_path) or os.path.exists(back_bytesio_path):
                        img = cv2.imread(back_bytesio_path) if back_bytesio_path else cv2.imread(back_temp_path)
                        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                        back_d = pytesseract.image_to_data(rgb, output_type=pytesseract.Output.DICT, lang="eng+hin")
                        temp = False
                        data["page_count"] = 2
                        data["back_file_type"] = back_suffix
                        count, ad, an = 0, 0, 0
                        flag=False
                        for i in range(0, len(back_d["text"])):
                            text = back_d["text"][i]
                            conf = int(float(back_d["conf"][i]))
                            if text not in keywords and conf > 80 and re.match(r'[a-zA-Z-0-9]', text):
                                if not flag:
                                  if re.match(r'^\d{6}$',text):
                                     flag=True
                                     continue
                                if re.match(r"^[SWD]/O:|Address(:)?", text) or temp:
                                    temp = True
                                    if re.match(r"Address(:)?", text):
                                        continue
                                    if count == 0:
                                        data["father_or_husband_name"] = text
                                    elif count == 1:
                                        data["father_or_husband_name"] += " " + text.replace(",", "")
                                    elif count > 1:
                                        if not re.match(r'^\d{4}$', text):
                                            if ad == 0:
                                                data["address"] = text
                                            else:
                                                data["address"] += " " + text
                                            ad += 1
                                        else:
                                            if an == 0:
                                                data["aadhaar_number"] = text
                                            elif 0 < an < 3:
                                                data["aadhaar_number"] += " " + text
                                            an += 1
                                    count += 1
                        if back_bytesio_path:
                            if os.path.exists(back_bytesio_path):
                                os.remove(back_bytesio_path)
                        else:
                            back_filename = "Back_" + data["name"].split()[0] + "_" + data["aadhaar_number"].replace(" ","") + "." + back_suffix
                            back_path = os.path.join(address + "aadhaar/", back_filename)
                            if not os.path.exists(back_path):
                                os.rename(back_temp_path, back_path)
                            data["back_file_path"]=url.format("aadhaar")+back_filename
                data["aadhaar_number"] = " ".join(list(OrderedDict.fromkeys(data["aadhaar_number"].split())))
                #pprint(data)
                front_filename = "Front_" + data["name"].split()[0] + "_" + data["aadhaar_number"].replace(" ","") + "." + front_suffix
                front_path = os.path.join(address + "aadhaar/", front_filename)
                if not os.path.exists(front_path) and os.path.exists(front_temp_path):
                    os.rename(front_temp_path, front_path)
                data["front_file_path"]= url.format("aadhaar") + front_filename
                return jsonify(data)
            except Exception as e:
                print(sys.exc_info()[-1].tb_lineno, " ", e)
                if os.path.exists(front_temp_path):
                   os.remove(front_temp_path)
                if back_temp_path:
                    if os.path.exists(back_temp_path):
                       os.remove(front_temp_path)
                return "Aadhaar card not readable",201
        if os.path.exists(front_temp_path):
            os.remove(front_temp_path)
        if back_temp_path:
            if os.path.exists(back_temp_path):
                os.remove(front_temp_path)
        return "Please submit valid file", 201