import pytesseract,re,pdf2image,os,traceback,cv2
from flask import request, jsonify, render_template
from PDFTextExtract import get_pdf_images
from PIL import Image
from io import BytesIO
from flask_cors import cross_origin
from werkzeug.utils import secure_filename
from preprocessing import get_preprocessed_file, detection,remove_nonsense,get_preprocessed_txt,read_image
from datetime import date
from pyaadhaar.decode import AadhaarSecureQr,AadhaarOldQr
from collections import OrderedDict
from app import app, mongo, s3
from dotenv import load_dotenv

load_dotenv()

suffixes = ("pdf", "jpeg", "png", "jpg")
pytesseract.pytesseract.tesseract_cmd=os.getenv("TESSERACT_PATH")
url = "https://{}.s3.{}.amazonaws.com/{}/{}"
region=s3.get_bucket_location(Bucket=os.getenv('AWS_BUCKET_NAME'))['LocationConstraint']


def uploaded_file_to_bytes(file):
    return BytesIO(file.read())


def reset_file(file):
    file.seek(0)
    return file


def image_to_bytes(image, image_format="JPEG"):
    file = BytesIO()
    image.save(file, format=image_format)
    file.seek(0)
    return file


def first_pdf_page_to_image_file(pdf_file):
    pdf_file.seek(0)
    imgs = get_pdf_images(pdf_file)
    if imgs:
        _, _, data = imgs[0]
        return BytesIO(data)

    pdf_file.seek(0)
    images = pdf2image.convert_from_bytes(pdf_file.read(), poppler_path=os.getenv("POPPLER_PATH"))
    return image_to_bytes(images[0])


def pdf_pages_to_image_files(pdf_file):
    pdf_file.seek(0)
    imgs = get_pdf_images(pdf_file)
    if imgs:
        return [BytesIO(data) for _, _, data in imgs]

    pdf_file.seek(0)
    images = pdf2image.convert_from_bytes(pdf_file.read(), poppler_path=os.getenv("POPPLER_PATH"))
    return [image_to_bytes(image) for image in images]


def upload_file_to_s3(file, folder, filename, content_type):
    bucket = os.getenv("AWS_BUCKET_NAME")
    key = f"{folder}/{filename}"
    s3.upload_fileobj(reset_file(file),bucket,key,ExtraArgs={
        "ContentType":content_type
    })
    private_url = url.format(bucket,region,folder,filename)
    presigned_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=600
    )
    return private_url, presigned_url


def presigned_url_from_private_url(private_url):
    if not private_url:
        return None
    bucket = os.getenv("AWS_BUCKET_NAME")
    prefix = f"https://{bucket}.s3.{region}.amazonaws.com/"
    key = private_url.replace(prefix, "", 1)
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=600
    )


def presign_record_urls(record, fields):
    data = record.copy()
    data["_id"] = str(data["_id"])
    for field in fields:
        if data.get(field):
            data[field] = presigned_url_from_private_url(data[field])
    return data


def json_response(data, status=200):
    return jsonify(data), status


def error_response(message, status):
    return jsonify({"message": message}), status

@app.route("/")
@cross_origin()
def index():
    return render_template("index.html")


@app.route("/pan_ocr",methods=["POST"])
@cross_origin()
def pan_ocr():
    if request.method=="POST":
        try:
            file=request.files["file"]
            suffix = file.filename.split(".")[1].lower()
            content_type=file.content_type
            file_bytes = uploaded_file_to_bytes(file)
            keywords="INCOME TAX DEPARTMENT GOVT. INDIA".split()
            if suffix in suffixes:
                if suffix == "pdf":
                    file = first_pdf_page_to_image_file(file_bytes)
                else:
                    file=file_bytes
                processed_file = get_preprocessed_file(file=file)
                txt = get_preprocessed_txt(pytesseract.image_to_string(processed_file, lang="eng+hin"))
                try:
                    pan_no = re.search(r"[A-Z]{5}[0-9oO]{4}[A-Z]", txt,flags=re.IGNORECASE).group(0).upper()
                    num = re.search(r"[0-9oO]{4}", pan_no).group(0)
                    if "o" in num or "O" in num:
                        pan_no = pan_no.replace(num, num.replace("o", "0").replace("O", "0"))
                except:
                    traceback.print_exc()
                    pan_no = None
                if pan_no:
                    existing_pan=mongo.db.pan.find_one({"pan_number":pan_no})
                    if existing_pan:
                        return json_response(presign_record_urls(existing_pan, ["url"]))
                names = list(filter(lambda x:len(x)>2 and not any(i in x for i in keywords),re.findall(r"\b[A-Z\.]+(?:[ \r\t\f]+[A-Z\.]+)*\b", txt)))
                names=list(filter(remove_nonsense,names))
                if len(names)>1:
                    customer_name=names[0]
                    father_name=names[1]
                    pan_type="Individual"
                    if re.search(customer_name,txt).end()+1==re.search(father_name,txt).start():
                        customer_name+=" "+father_name
                        try:
                            father_name=names[2]
                        except:
                            traceback.print_exc()
                            father_name=None
                            pan_type="Business"
                else:
                    customer_name=names[0]
                    father_name=None
                    pan_type="Business"
                try:
                    dob = re.search(r"(\d+/\d+/\d+)", txt).group(0)
                except:
                    traceback.print_exc()
                    dob = None
                filename = secure_filename(customer_name.split()[0]+"_"+pan_no+ "." + suffix)
                private_url, presigned_url = upload_file_to_s3(file_bytes, "pan", filename, content_type)
                data={"name":customer_name,"father_name":father_name,"pan_number":pan_no,
                      "pan_type":pan_type,"date_of_birth_or_registration":dob,
                      "url":private_url}
                mongo.db.pan.insert_one(data)
                data["_id"]=str(data["_id"])
                response_data = data.copy()
                response_data["url"] = presigned_url
                return json_response(response_data, 201)
            return error_response("Please submit valid file", 415)
        except:
            traceback.print_exc()
            return error_response("Something went wrong", 500)

@app.route("/dl_ocr",methods=["POST"])
@cross_origin()
def dl_ocr():
    if request.method=="POST":
        file = request.files["file"]
        suffix = file.filename.split(".")[1].lower()
        content_type=file.content_type
        file_bytes = uploaded_file_to_bytes(file)
        keywords = "NCT DOB".split()
        if suffix in suffixes:
            if suffix == "pdf":
                file = first_pdf_page_to_image_file(file_bytes)
            else:
                file=file_bytes
            file = get_preprocessed_file(file=file)
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
                traceback.print_exc()
                dl_no = None
            if dl_no:
                existing_dl=mongo.db.dl.find_one({"dl_number":dl_no})
                if existing_dl:
                    return json_response(presign_record_urls(existing_dl, ["file_path"]))
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
                traceback.print_exc()
                dob = None
                validity = None
            try:
                bg = re.sub(r"(Blood Group|B[.]?G[.]?)[\s]?[:.]?[\s]", "",re.search(r"(Blood Group|B[.]?G[.]?)[\s]?[:.]?[\s](\w+)", txt, flags=re.IGNORECASE).group(0),flags=re.IGNORECASE)
                if len(bg) > 3:
                    bg = "U"
            except:
                traceback.print_exc()
                bg = None
            try:
                dl_address = re.split(r"(Address|ress)[\s]?[:.]?[\s]", txt, flags=re.IGNORECASE)[2].split("\n\n")[0].replace("\n", " ")
            except:
                traceback.print_exc()
                dl_address = None
            filename = customer_name.split()[0] + "_" + re.sub(r"[\s-]","",dl_no) + "." + suffix
            private_url, presigned_url = upload_file_to_s3(file_bytes, "dl", filename, content_type)
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
                "file_path": private_url
            }
            mongo.db.dl.insert_one(data)
            data["_id"]=str(data["_id"])
            response_data = data.copy()
            response_data["file_path"] = presigned_url
            return json_response(response_data, 201)
        return error_response("Please submit valid file", 415)


@app.route("/aadhaar_ocr",methods=["POST"])
@cross_origin()
def aadhaar_ocr():
    if request.method=="POST":
        front_file=request.files["front_file"]
        back_file=request.files.get("back_file",None)
        front_suffix = front_file.filename.split(".")[1].lower()
        front_content_type=front_file.content_type
        front_file_bytes = uploaded_file_to_bytes(front_file)
        if back_file:
            back_suffix = back_file.filename.split(".")[1].lower()
            back_content_type=back_file.content_type
            back_file_bytes = uploaded_file_to_bytes(back_file)
        else:
            back_suffix,back_content_type,back_file_bytes=None,None,None
        if front_suffix in suffixes or back_suffix in suffixes:
            back_image_file = None
            if front_suffix == "pdf":
                try:
                    images = pdf_pages_to_image_files(front_file_bytes)
                    front_image_file = images[0]
                    if back_file is None and len(images) > 1:
                        back_image_file = images[1]
                except:
                    traceback.print_exc()
                    return error_response("PDF is password protected", 422)
            else:
               front_image_file = front_file_bytes
            if back_file:
                back_image_file = first_pdf_page_to_image_file(back_file_bytes) if back_suffix == "pdf" else back_file_bytes
            front_qr_code=detection(front_image_file)
            img = read_image(front_image_file)
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            front_d = pytesseract.image_to_data(rgb, output_type=pytesseract.Output.DICT, lang="eng+hin")
            txt=pytesseract.image_to_string(Image.open(reset_file(front_image_file)), lang="eng+hin")
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
               if aadhaar_number:
                   existing_aadhaar=mongo.db.aadhaar.find_one({"aadhaar_number":aadhaar_number})
                   if existing_aadhaar:
                       return json_response(presign_record_urls(existing_aadhaar, ["front_file_path", "back_file_path"]))
               front_filename = "Front_"+d["name"].split()[0] + "_" + aadhaar_number.replace(" ","") + "." + front_suffix
               front_private_url, front_presigned_url = upload_file_to_s3(front_file_bytes, "aadhaar", front_filename, front_content_type)
               if back_file:
                   back_filename = "Back_" + d["name"].split()[0] + "_" + aadhaar_number.replace(" ","") + "." + back_suffix
                   back_private_url, back_presigned_url = upload_file_to_s3(back_file_bytes, "aadhaar", back_filename, back_content_type)
               else:
                   back_private_url, back_presigned_url = None, None
               data = {"name": d["name"], "aadhaar_number":aadhaar_number,
                       "gender": "Male" if d["gender"] == "M" else "Female" if d["gender"] == "F" else "Transgender",
                       "father_or_husband_name": fh,
                       "date_or_year_of_birth": d["dob"].replace("-","/") if d.get("dob", None) else d["yob"],
                       "address": aadhaar_address,
                       "page_count":2 if back_file else 1, "front_file_type":front_suffix, "back_file_type":back_suffix,
                       "front_file_path":front_private_url,
                       "back_file_path":back_private_url}
               mongo.db.aadhaar.insert_one(data)
               data["_id"]=str(data["_id"])
               response_data = data.copy()
               response_data["front_file_path"] = front_presigned_url
               response_data["back_file_path"] = back_presigned_url
               return json_response(response_data, 201)
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
                if data.get("aadhaar_number"):
                    existing_aadhaar=mongo.db.aadhaar.find_one({"aadhaar_number":data["aadhaar_number"]})
                    if existing_aadhaar:
                        return json_response(presign_record_urls(existing_aadhaar, ["front_file_path", "back_file_path"]))
                if back_image_file:
                    if back_image_file:
                        img = read_image(back_image_file)
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
                        if back_file:
                            back_filename = "Back_" + data["name"].split()[0] + "_" + data["aadhaar_number"].replace(" ","") + "." + back_suffix
                            data["back_file_path"], back_presigned_url=upload_file_to_s3(back_file_bytes, "aadhaar", back_filename, back_content_type)
                data["aadhaar_number"] = " ".join(list(OrderedDict.fromkeys(data["aadhaar_number"].split())))
                if data.get("aadhaar_number"):
                    existing_aadhaar=mongo.db.aadhaar.find_one({"aadhaar_number":data["aadhaar_number"]})
                    if existing_aadhaar:
                        return json_response(presign_record_urls(existing_aadhaar, ["front_file_path", "back_file_path"]))
                #pprint(data)
                front_filename = "Front_" + data["name"].split()[0] + "_" + data["aadhaar_number"].replace(" ","") + "." + front_suffix
                data["front_file_path"], front_presigned_url= upload_file_to_s3(front_file_bytes, "aadhaar", front_filename, front_content_type)
                mongo.db.aadhaar.insert_one(data)
                data["_id"]=str(data["_id"])
                response_data = data.copy()
                response_data["front_file_path"] = front_presigned_url
                if back_file:
                    response_data["back_file_path"] = back_presigned_url
                return json_response(response_data, 201)
            except Exception as e:
                traceback.print_exc()
                return error_response("Aadhaar card not readable", 422)
        return error_response("Please submit valid file", 415)
