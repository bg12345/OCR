import pytesseract,re,pdf2image,os,tabula
from flask import request, jsonify
from PDFTextExtract import get_pdf_images
from io import BytesIO
from flask_cors import cross_origin
from preprocessing import get_preprocessed_file
from datetime import date
from bson.objectid import ObjectId
from model.mongodb import mongo
from app import app

pytesseract.pytesseract.tesseract_cmd=r"C:\Program Files\Tesseract-OCR\tesseract.exe"
suffixes = ("pdf", "jpeg", "png", "jpg")
db = mongo.db.data


@app.route("/pan", methods=["POST"])
@cross_origin()
def pan():
    if request.method == "POST":
        username = request.form["username"]
        name=username.upper()
        file = request.files["file"]
        suffix = file.filename.split(".")[1].lower()
        page_count = request.form["page_count"]
        if suffix in suffixes:
            if suffix == "pdf":
                imgs = get_pdf_images(file)
                if len(imgs) == int(page_count) == 1:
                    (mode, size, data) = imgs[0]
                    file = BytesIO(data)
            file = get_preprocessed_file(file)
            txt = re.sub(' +', ' ', pytesseract.image_to_string(file,lang="eng+hin").replace("\n", " "))
            print(txt)
            if any([i.lower() in txt.lower() for i in "Permanent Account Number Card INCOME TAX DEPARTMENT INDIA".split()]):
                if any([re.search(i[:4], txt, flags=re.IGNORECASE) for i in " ".join(list(filter(lambda x:len(x) >= 4, username.split()))).split(maxsplit=1)]):
                    try:
                        n = re.findall(r"\b[A-Z]+(?:\s+[A-Z]+)*\b", txt)
                        try:
                            pan_no = re.search(r"[A-Z]{5}[0-9oO]{4}[A-Z]", txt).group(0)
                            num = re.search(r"[0-9oO]{4}", pan_no).group(0)
                            if "o" in num or "O" in num:
                                pan_no = pan_no.replace(num, num.replace("o", "0").replace("O", "0"))
                        except:
                            pan_no = "Not readable"
                        pan_existing = db.find_one({"$and":[{"pan.name":name},{"pan.pan_number":pan_no}]})
                        if pan_existing:
                            pan_existing["pan"]["_id"]=str(pan_existing["_id"])
                            return jsonify(pan_existing["pan"])
                        try:
                            dob = re.search(r"(\d+/\d+/\d+)", txt).group(0)
                        except:
                            dob = "Not readable"
                        father_name = "Not readable"
                        try:
                            if len(n[-1].split(name)[-1]) <= 2:
                                data = {
                                    "name": name,
                                    "date_of_registration": dob,
                                    "pan_number": pan_no,
                                    "pan_type": "Bussiness",
                                    "page_count": page_count,
                                    "file_type":suffix
                                }
                                db.insert_one({"pan":data})
                                return jsonify(data)
                            for i in range(n.index(name)+1, len(n)):
                                if len(n[i]) > 1:
                                    father_name = n[i]
                                    break
                        except:
                            for i in n:
                                if name in i:
                                    father_name = " ".join(i.split(name)[1].split())
                                    if len(father_name) <= 2:
                                        father_name = n[n.index(i)+1]
                                    break
                        data = {
                            "name": name,
                            "father_name": father_name,
                            "date_of_birth": dob,
                            "pan_number": pan_no,
                            "pan_type": "Individual",
                            "page_count": page_count,
                            "file_type":suffix
                        }
                        aadhaar_existing = db.find_one({"$and":[{"aadhaar.name": data["name"]},{"aadhaar.date_of_birth":data["date_of_birth"]}]})
                        dl_existing = db.find_one({"$and":[{"driving_licence.name": data["name"]},{"driving_licence.date_of_birth":data["date_of_birth"]}]})
                        if aadhaar_existing:
                            db.update_one({"_id": aadhaar_existing["_id"]}, {"$set": {"pan":data}})
                            data["_id"]=str(aadhaar_existing["_id"])
                        elif dl_existing:
                            db.update_one({"_id": dl_existing["_id"]}, {"$set": {"pan":data}})
                            data["_id"] = str(dl_existing["_id"])
                        else:
                            data={"pan": data}
                            db.insert_one(data)
                            data["pan"]["_id"]=str(data["_id"])
                            data=data["pan"]
                        return jsonify(data)
                    except:
                        return "Pan Card not readable", 201
                return "User Verification failed", 201
            return "Please submit Pan document", 201
        return "Please submit valid file", 201

@app.route("/pan_update",methods=["POST"])
@cross_origin()
def pan_update():
    if request.method=="POST":
        data=request.get_json()
        pan_existing = db.find_one({"_id": ObjectId(data["_id"])})
        data.pop("_id")
        if data["pan_type"]=="Individual":
            aadhaar_existing = db.find_one({"$and": [{"aadhaar.name": data["name"]}, {"aadhaar.date_of_birth": data["date_of_birth"]}]})
            dl_existing = db.find_one({"$and": [{"driving_licence.name": data["name"]},{"driving_licence.date_of_birth": data["date_of_birth"]}]})
            if aadhaar_existing:
                db.update_one({"_id": aadhaar_existing["_id"]}, {"$set": {"pan": data}})
                if pan_existing:
                    if aadhaar_existing["_id"] != pan_existing["_id"]:
                       db.remove({"_id":pan_existing["_id"]})
            elif dl_existing:
                db.update_one({"_id": dl_existing["_id"]}, {"$set": {"pan": data}})
                if pan_existing:
                    if dl_existing["_id"] != pan_existing["_id"]:
                       db.remove({"_id":pan_existing["_id"]})
            elif pan_existing:
                db.update_one({"_id":pan_existing["_id"]},{"$set":{"pan":data}})
            else:
                return "Unsuccessful", 201
            return "Data Updated Successfully", 200
        else:
            if pan_existing:
                db.update_one({"_id":pan_existing["_id"]},{"$set":{"pan":data}})
                return "Data Updated Successfully", 200
            return "Unsuccessful", 201


@app.route("/aadhaar", methods=["POST"])
@cross_origin()
def aadhaar():
    if request.method == "POST":
        username = request.form["username"]
        name=username.upper()
        front_file = request.files["front_file"]
        front_suffix = front_file.filename.split(".")[1].lower()
        try:
            back_file = request.files["back_file"]
            back_suffix = back_file.filename.split(".")[1].lower()
        except:
            back_file = None
            back_suffix = None
        page_count = request.form["page_count"]
        if front_suffix in suffixes or back_suffix in suffixes:
            if back_file is None and front_suffix == "pdf":
                imgs = get_pdf_images(front_file)
                (mode, size, data) = imgs[0]
                front_file = BytesIO(data)
                if len(imgs) == int(page_count) == 2:
                    (mode, size, data) = imgs[1]
                    back_file = BytesIO(data)
                else:
                    return "Not valid file", 201
            front_file = get_preprocessed_file(front_file)
            front_txt = re.sub(" +", " ", re.sub(r"[^a-zA-Z0-9\s:,\-/]+", "", pytesseract.image_to_string(front_file, lang="eng+hin")).replace("\n", " ")).replace(" , , ", " ")
            # print(front_txt)
            # print(re.sub(r"[^a-zA-Z0-9\s:,\-/]+","",pytesseract.image_to_string(front_file,lang="eng+hin")).replace("\n"," "))
            try:
                back_file = get_preprocessed_file(back_file)
                back_txt = re.sub(" +", " ", re.sub(r"[^a-zA-Z0-9\s:.,\-/]+", "", pytesseract.image_to_string(back_file, lang="eng+hin")).replace("\n", "")).replace(" , , ", " ")
                # print(back_txt)
            except:
                back_txt = None
                if any([i.lower() in front_txt.lower() for i in "Unique Identification Authority".split()]):
                    back_txt = front_txt
            data = {}
            print(front_txt)
            if any([re.search(i[:4], front_txt, flags=re.IGNORECASE) for i in " ".join(list(filter(lambda x:len(x) >= 4, username.split()))).split(maxsplit=1)]):
                try:
                    data["name"] = name
                    if back_txt != front_txt:
                        try:
                            data["date_of_birth"] = re.search(r"(\d+/\d+/\d+)", front_txt).group(0)
                        except:
                            try:
                                data["year_of_birth"] = re.search(r": (\w+)|:(\w+)", front_txt).group(0).replace(":", " ").split(" ")[-1]
                            except:
                                data["year_of_birth"] = "Not readable"
                    else:
                        try:
                            data["mobile_number"] = re.sub(r"[:.\s]", "", re.search(r"([^A-Z]+)[0-9oO]{9,10}[\s]?[0-9oO]?", back_txt, flags=re.IGNORECASE).group(0))
                            if "o" in data["mobile_number"] or "O" in data["mobile_number"]:
                                data["mobile_number"] = re.sub(r"[oO]", "0", data["mobile_number"])
                        except:
                            data["mobile_number"] = "Not readable"
                        try:
                            data["pin_code"] = re.sub(r"PIN Code[\s]?[:.]? ", "", re.search(r"PIN Code[\s]?[:.]? [0-9oO]{6}", back_txt).group(0))
                            num = re.search(r"[0-9oO]{4}", data["pin_code"]).group(0)
                            if "o" in num or "O" in num:
                                data["pin_code"] = data["pin_code"].replace(num, num.replace("o", "0").replace("O", "0"))
                        except:
                            data["pin_code"] = "Not Readable"
                    temp_name = None
                    if back_txt is not None:
                        if "S/O" in back_txt:
                            try:
                                data["father_name"] = re.sub(r"S/O[\s]?[:.]? ", "", re.search(r"S/O[\s]?[:.]? [A-Z\s]+,", back_txt, flags=re.IGNORECASE).group(0)).replace(",", "").upper()
                            except:
                                data["father_name"] = "Not Readable"
                            temp_name = data["father_name"]
                        elif "D/O" in back_txt:
                            try:
                                data["father_name"] = re.sub(r"D/O[\s]?[:.]? ", "", re.search(r"D/O[\s]?[:.]? [A-Z\s]+,", back_txt, flags=re.IGNORECASE).group(0)).replace(",", "").upper()
                            except:
                                data["father_name"] = "Not Readable"
                            temp_name = data["father_name"]
                        elif "W/O" in back_txt:
                            try:
                                data["husband_name"] = re.sub(r"W/O[\s]?[:.]? ", "", re.search(r"W/O[\s]?[:.]? [A-Z\s]+,", back_txt, flags=re.IGNORECASE).group(0)).replace(",", "").upper()
                            except:
                                data["husband_name"] = "Not Readable"
                            temp_name = data["husband_name"]
                        try:
                            back_number = re.search(r"[0-9oO]{4} [0-9oO]{4} [0-9oO]{4}", back_txt[::-1]).group(0)
                            if "o" in back_number or "O" in back_number:
                                back_number = back_number.replace("o", "0").replace("O", "0")
                        except:
                            back_number = None
                    else:
                        back_number = None
                    try:
                        front_number = re.search(r"[0-9oO]{4} [0-9oO]{4} [0-9oO]{4}", front_txt[::-1]).group(0)
                        if "o" in front_number or "O" in front_number:
                            front_number = front_number.replace("o", "0").replace("O", "0")
                    except:
                        try:
                            front_number = re.search(r"[0-9oO]{4} [0-9oO]{4} [0-9oO]{4}", back_txt[::-1]).group(0)
                            if "o" in front_number or "O" in front_number:
                                front_number = front_number.replace("o", "0").replace("O", "0")
                        except:
                            front_number = "Not readable"
                    if "female" in front_txt.lower():
                        data["gender"] = "FEMALE"
                    elif "male" in front_txt.lower():
                        data["gender"] = "MALE"
                    elif "transgender" in front_txt.lower():
                        data["gender"] = "TRANSGENDER"
                    else:
                        data["gender"] = "Not Readable"
                    data["page_count"] = page_count
                    if front_number == back_number or back_number is None:
                        if front_number != "Not readable":
                            try:
                                if front_txt != back_txt:
                                    data["address"] = re.search(temp_name + ", (.*) " + front_number[::-1], back_txt).group(1)
                                else:
                                    data["address"] = back_txt.split(temp_name+", ")[1].split(",")[0]
                            except:
                                data["address"] = "Not readable"
                            data["aadhaar_number"] = front_number[::-1]
                        else:
                            data["aadhaar_number"] = front_number
                        data["file_type"]=front_suffix
                        aadhaar_existing = db.find_one({"$and":[{"aadhaar.name":name},{"aadhaar.aadhaar_number":data["aadhaar_number"]}]})
                        if aadhaar_existing:
                            aadhaar_existing["aadhaar"]["_id"] = str(aadhaar_existing["_id"])
                            return jsonify(aadhaar_existing["aadhaar"])
                        pan_existing = db.find_one({"$and": [{"pan.name": data["name"]}, {"pan.date_of_birth": data["date_of_birth"]}]})
                        dl_existing = db.find_one({"$and": [{"driving_licence.name": data["name"]},{"driving_licence.date_of_birth": data["date_of_birth"]}]})
                        if pan_existing:
                            db.update_one({"_id": pan_existing["_id"]}, {"$set": {"aadhaar":data}})
                            data["_id"] = str(pan_existing["_id"])
                        elif dl_existing:
                            db.update_one({"_id": dl_existing["_id"]}, {"$set": {"aadhaar":data}})
                            data["_id"] = str(dl_existing["_id"])
                        else:
                            data = {"aadhaar": data}
                            db.insert_one(data)
                            data["aadhaar"]["_id"] = str(data["_id"])
                            data = data["aadhaar"]
                        return jsonify(data)
                    return "Front and back don't match", 201
                except:
                    return "Aadhaar Card not readable", 201
            return "User verification failed", 201
        return "Please submit valid file", 201

@app.route("/aadhaar_update",methods=["POST"])
@cross_origin()
def aadhaar_update():
    if request.method=="POST":
        data=request.get_json()
        aadhaar_existing = db.find_one({"_id": ObjectId(data["_id"])})
        data.pop("_id")
        pan_existing = db.find_one({"$and": [{"pan.name": data["name"]}, {"pan.date_of_birth": data["date_of_birth"]}]})
        dl_existing = db.find_one({"$and": [{"driving_licence.name": data["name"]},{"driving_licence.date_of_birth": data["date_of_birth"]}]})
        if pan_existing:
            db.update_one({"_id": pan_existing["_id"]}, {"$set": {"aadhaar": data}})
            if aadhaar_existing:
                if aadhaar_existing["_id"]!=pan_existing["_id"]:
                   db.remove({"_id":aadhaar_existing["_id"]})
        elif dl_existing:
            db.update_one({"_id": dl_existing["_id"]}, {"$set": {"aadhaar": data}})
            if aadhaar_existing:
                if aadhaar_existing["_id"] != dl_existing["_id"]:
                   db.remove({"_id":aadhaar_existing["_id"]})
        elif aadhaar_existing:
            db.update_one({"_id":aadhaar_existing["_id"]},{"$set":{"aadhaar":data}})
        else:
            return "Unsuccessful", 201
        return "Data Updated Successfully", 200


@app.route("/driving_licence", methods=["POST"])
@cross_origin()
def driving_licence():
    if request.method == "POST":
        username = request.form["username"]
        name=username.upper()
        file = request.files["file"]
        page_count = request.form["page_count"]
        suffix = file.filename.split(".")[1].lower()
        if suffix in suffixes:
            if suffix == "pdf":
                imgs = get_pdf_images(file)
                if len(imgs) == int(page_count) == 1:
                    (mode, size, data) = imgs[0]
                    file = BytesIO(data)
            file = get_preprocessed_file(file)
            txt = pytesseract.image_to_string(file)
            # print(txt)
            if any([i.lower() in txt.lower() for i in "Transport Driving Licence".split()]):
                x = " ".join(list(filter(lambda x: len(x) >= 4, username.split()))).split(maxsplit=1)
                t = [re.search(i[:4], txt, flags=re.IGNORECASE) for i in x]
                if any(t):
                    try:
                        try:
                            dl_no = re.search(r"[A-Z]{2}[-]?[0-9oO]{2}[\s]?[0-9oO]{11}", txt).group(0)
                            num = re.search(r"[0-9oO]{2}[\s]?[0-9oO]{11}", dl_no).group(0)
                            if "o" in num or "O" in num:
                                dl_no = dl_no.replace(num, num.replace("o", "0").replace("O", "0"))
                        except:
                            dl_no = "Not Readable"
                        dl_existing = db.find_one({"$and":[{"driving_licence.name":name},{"driving_licence.pan_number":dl_no}]})
                        if dl_existing:
                            dl_existing["driving_licence"]["_id"] = str(dl_existing["_id"])
                            return jsonify(dl_existing["driving_licence"])
                        sdw = "Not Readable"
                        try:
                            temp = None
                            for i, j in enumerate(t):
                                if j:
                                    if i == 0:
                                        temp = re.split(re.search(txt[t[i].start():t[i].end()] + r"([A-Z]+)?[\s]?([A-Z]+)?", txt, flags=re.IGNORECASE).group(0), txt, flags=re.IGNORECASE, maxsplit=1)
                                    else:
                                        if " " not in x[1]:
                                            temp = re.split(re.search(r"([a-z]+)[\s]"+txt[t[i].start():t[i].end()]+r"([a-z]+)?", txt, flags=re.IGNORECASE).group(0), txt, flags=re.IGNORECASE, maxsplit=1)
                                        else:
                                            temp = re.split(re.search(x[1], txt, flags=re.IGNORECASE).group(0), txt, flags=re.IGNORECASE, maxsplit=1)
                                    break
                            # print(temp)
                            # print(re.findall(r"[:.]?[\s]?\b[A-Z]+(?:\s[A-Z]+)*\b",temp[1]))
                            for i in re.findall(r"[:.]?[\s]?\b[A-Z]+(?:\s[A-Z]+)*\b", temp[1]):
                                if len(i) > 2:
                                    sdw = re.sub(r"^[:.]?[\s]?[N]?[\s]?", "", i)
                                    break
                        except:
                            pass
                        try:
                            dates = [j for i in re.findall(r"(\d+/\d+/\d+)|(\d+-\d+-\d+)", txt) for j in i if j != ""]
                            # print(dates)
                            dates = [i for i in dates if dates.count(i) == 1]
                            # print(dates)
                            dates = {i: date.today().year - int(re.split(r"[-/]", i)[-1]) for i in dates}
                            dob = max(dates, key=dates.get).replace("-","/")
                            validity = min(dates, key=dates.get).replace("-","/")
                            issue_date = "Not Readable"
                            for i in dates:
                                if i != dob and i != validity:
                                    issue_date = i.replace("-","/")
                                    break
                        except:
                            dob = "Not Readable"
                            validity = "Not Readable"
                            issue_date = "Not Readable"
                        try:
                            bg = re.sub(r"(Blood Group|B[.]?G[.]?)[\s]?[:.]?[\s]", "", re.search(r"(Blood Group|B[.]?G[.]?)[\s]?[:.]?[\s](\w+)", txt, flags=re.IGNORECASE).group(0), flags=re.IGNORECASE)
                            if len(bg) > 3:
                                bg = "U"
                        except:
                            bg = "Not Readable"
                        try:
                            address = re.split(r"(Address|ress)[\s]?[:.]?[\s]", txt, flags=re.IGNORECASE)[2].split("\n\n")[0].replace("\n", " ")
                        except:
                            address = "Not Readable"
                        data={
                            "name":name,
                            "dl_no":dl_no,
                            "date_of_birth":dob,
                            "issue_date":issue_date,
                            "validity":validity,
                            "address":address,
                            "sdw":sdw,
                            "blood_group":bg,
                            "page_count":page_count,
                            "file_type":suffix
                        }
                        pan_existing = db.find_one({"$and": [{"pan.name": data["name"]}, {"pan.date_of_birth": data["date_of_birth"]}]})
                        aadhaar_existing = db.find_one({"$and": [{"aadhaar.name": data["name"]},{"aadhaar.date_of_birth": data["date_of_birth"]}]})
                        if pan_existing:
                            db.update_one({"_id": pan_existing["_id"]}, {"$set": {"driving_licence":data}})
                            data["_id"] = str(pan_existing["_id"])
                        elif aadhaar_existing:
                            db.update_one({"_id": aadhaar_existing["_id"]}, {"$set": {"driving_licence":data}})
                            data["_id"] = str(aadhaar_existing["_id"])
                        else:
                            data = {"driving_licence": data}
                            db.insert_one(data)
                            data["driving_licence"]["_id"] = str(data["_id"])
                            data = data["driving_licence"]
                        return jsonify(data)
                    except:
                        return "Driving Licence not readable", 201
                return "User verification failed", 201
            return "Please submit DL document", 201
        return "Please submit valid file", 201

@app.route("/driving_licence_update",methods=["POST"])
@cross_origin()
def driving_licence_update():
    if request.method=="POST":
        data=request.get_json()
        dl_existing = db.find_one({"_id": ObjectId(data["_id"])})
        data.pop("_id")
        pan_existing = db.find_one({"$and": [{"pan.name": data["name"]}, {"pan.date_of_birth": data["date_of_birth"]}]})
        aadhaar_existing = db.find_one({"$and": [{"aadhaar.name": data["name"]},{"aadhaar.date_of_birth": data["date_of_birth"]}]})
        if pan_existing:
            db.update_one({"_id": pan_existing["_id"]}, {"$set": {"driving_licence": data}})
            if dl_existing:
                if dl_existing["_id"] != pan_existing["_id"]:
                   db.remove({"_id":dl_existing["_id"]})
        elif aadhaar_existing:
            db.update_one({"_id": aadhaar_existing["_id"]}, {"$set": {"driving_licence": data}})
            if dl_existing:
                if aadhaar_existing["_id"] != dl_existing["_id"]:
                   db.remove({"_id":dl_existing["_id"]})
        elif dl_existing:
            db.update_one({"_id":dl_existing["_id"]},{"$set":{"driving_licence":data}})
        else:
            return "Unsuccessful", 201
        return "Data Updated Successfully", 200


address = os.path.dirname(os.path.dirname(os.getcwd())) + "/E Learning/ocr_project/doc_files/bank/"
# address=os.path.dirname(os.path.dirname(os.getcwd()))+"/model/"


@app.route('/bank', methods=['POST'])
@cross_origin()
def upload_bank_file():
    #a.logger.info('Application information: Info level logs...')
    file = request.files["file"]
    path = os.path.join(address, file.filename)
    file.save(path)

 # --------------_Data extraction begin ------------------

    bankName = ['HDFC', 'ICICI']
    # filepath = os.path.join(upload_directory_bank, filename)
    # images = convert_from_path(filepath)
    images = pdf2image.convert_from_path(path)
    extractedOutput = pytesseract.image_to_string(images[0])
    finalResult = []

    def hdfcBank(path):
        keywords = {'Registered Office Address', 'Generated On',
                    'State account branch GSTN', 'Requesting Branch Code'}
        # images = convert_from_path(path)
        finalResult = []
        for x, image in enumerate(images):
            result = dict()

            extractedOutput = pytesseract.image_to_string(image)
            output = extractedOutput
            extractedOutput = extractedOutput.replace('»', ':')
            extractedOutput = extractedOutput.replace(
                'We understand your world ', '')
            extractedOutput = extractedOutput.split('\n')

            visited = set()
            flag = False
            for lines in extractedOutput:
                for key in keywords:
                    if ':' in lines:
                        if key in lines and key not in visited:
                            index = lines.index(key)
                            a = lines.split(':')
                            result[key] = a[-1]
                            visited.add(key)
                            break
            box = [2.76, 0.68, 6.7, 11]
            for i in range(0, len(box)):
                box[i] *= 28.28
            customer_df = tabula.read_pdf(
                path, pages=x+1, area=box, output_format='json')
            customer_data = []
            for file in customer_df[0]['data']:
                customer_data.append(file[0]['text'])
            result['Customer Info'] = customer_data

            box = [1.67, 11.58, 7.02, 19.19]
            for i in range(0, len(box)):
                box[i] *= 28.28
            statement_df = tabula.read_pdf(
                path, pages=x+1, area=box, output_format='json', stream=True)
            newDic = dict()

            for file in statement_df[0]['data']:
                flag = False
                for i, context in enumerate(file):
                    if i == 0 and context['text'] != '':
                        key = context['text'][:-1]
                        newDic[context['text'][:-1]] = ''
                    elif i == 0 and context['text'] == '':
                        flag = True

                    else:
                        if flag:
                            newDic[key] += ' '+context['text']
                        else:
                            newDic[key] += ' '+context['text']
            result['BillInfo'] = newDic
            table = tabula.read_pdf(
                path, pages=x+1, pandas_options={'header': None})
            if table:
                colNumber = table[0].shape[1]

                if x == 0:
                    cols = table[0].values.tolist()[0]
                    table[0] = table[0].iloc[1:]
                else:
                    if table[0].columns[0] == 'Date':
                        table[0] = table[0].iloc[1:]

                rowNumber = table[0].shape[0]
                if x == 0:
                    rowNumber += 1

                table[0] = table[0].fillna('None')
                res = []

                for i in range(1, rowNumber):
                    dic = {}

                    if table[0][0][i] != 'None':

                        for k, columns in enumerate(cols):
                            # #print(k,colNumber)
                            if colNumber <= 6:
                                if k >= 6:
                                    break
                                elif k == 5:
                                    dic['Closing Bal.'] = table[0][k][i]

                                else:
                                    dic[columns] = table[0][k][i]
                            else:
                                dic[columns] = table[0][k][i]

                        res.append(dic)
                flag = False
                for i in range(1, table[0].shape[0]):
                    if table[0][1][i] == 'Opening Balance':
                        flag = True
                        break

                if flag:

                    result['Opening Balance'] = table[0][1][i+1]
                    result['Dr Count'] = table[0][2][i+1]
                    result['Cr Count'] = table[0][3][i+1]
                    result['Debits Credits'] = table[0][4][i+1]
                    result['Closing Bal'] = table[0][5][i+1]

                result['Statement of Account'] = res
            finalResult.append(result)
            # p#print.p#print(result)
            # print(result)
        return finalResult

    def iciciBank(path):
        # images = convert_from_path(path)
        finalResult = []
        keywords = ['Account Number', 'Transaction Date', 'Transaction Period', 'Advanced Search',
                    'Amount', 'Cheque number', 'Transaction remarks', 'Transaction type', 'Transactions List']
        for x, image in enumerate(images):
            result = dict()

            box = [5.18, 5.46, 12.90, 20.78]

            for i in range(len(box)):
                box[i] *= 28.28

            customer_info = tabula.read_pdf(
                path, pages=1, area=box, output_format="json", stream=True)
            customer_info = customer_info[0]['data']

            for fields in customer_info:
                # #print(result)
                for i, data in enumerate(fields):
                    if i == 0:
                        for key in keywords:
                            if key in data['text']:
                                ind = data['text'].index(key)
                                length = len(key)
                                result[key] = data['text'][ind+length+1:]
                                break
                    else:
                        try:
                            result[key] += data['text']
                        except:
                            pass
            result['Account Summary'] = []
            table = tabula.read_pdf(path, pages=x+1)
            length = len(table[0].columns)
            table[0].columns = list(range(length))
            if table:
                table = table[0].dropna(how='all')
                if x == 0:
                    cols = table.iloc[0, :].values
                    table = table.iloc[1:, :]
                table = table.reset_index()
                for j in range(table.shape[0]):
                    res = {}
                    for k in range(length):
                        text = table[k][j]
                        if isinstance(text, str):
                            text = text.replace('\r', ' ')
                        res[cols[k]] = text
                    result['Account Summary'].append(res)

            # p#print.p#print(result)
            # print(result)
            finalResult.append(result)
        return finalResult

        # def axisBank(path):
        # # images = convert_from_path(path)
        # images = pdf2image.convert_from_path(filepath)
        # finalResult = []
        # keywords = ['Account Number','Transaction Date','Transaction Period','Advanced Search','Amount','Cheque number','Transaction remarks','Transaction type','Transactions List']
        # for x,image in enumerate(images):
        # 	result = dict()

        # 	box = [5.18,5.46,12.90,20.78]

        # 	for i in range(len(box)):
        # 		box[i] *= 28.28

        # 	customer_info = tabula.read_pdf(path,pages = 1,area=box,output_format="json",stream=True)
        # 	customer_info = customer_info[0]['data']

        # 	for fields in customer_info:
        # 		##print(result)
        # 		for i,data in enumerate(fields):
        # 			if i == 0:
        # 				for key in keywords:
        # 					if key in data['text']:
        # 						ind = data['text'].index(key)
        # 						length = len(key)
        # 						result[key] = data['text'][ind+length+1:]
        # 						break
        # 			else:
        # 				try:
        # 					result[key] += data['text']
        # 				except:
        # 					pass
        # 	result['Account Summary'] = []
        # 	table = tabula.read_pdf(path,pages=x+1)
        # 	length = len(table[0].columns)
        # 	table[0].columns = list(range(length))
        # 	if table:
        # 		table = table[0].dropna(how='all')
        # 		if x == 0:
        # 			cols = table.iloc[0,:].values
        # 			table = table.iloc[1:,:]
        # 		table = table.reset_index()
        # 		for j in range(table.shape[0]):
        # 			res = {}
        # 			for k in range(length):
        # 				text = table[k][j]
        # 				if isinstance(text,str):
        # 					text = text.replace('\r',' ')
        # 				res[cols[k]] = text
        # 			result['Account Summary'].append(res)

        # 	# p#print.p#print(result)
        # 	#print(result)
        # 	finalResult.append(result)
        # return finalResult

        # def sbiBank(path):
        # # images = convert_from_path(path)
        # images = pdf2image.convert_from_path(filepath)
        # finalResult = []
        # keywords = ['Account Number','Transaction Date','Transaction Period','Advanced Search','Amount','Cheque number','Transaction remarks','Transaction type','Transactions List']
        # for x,image in enumerate(images):
        # 	result = dict()

        # 	box = [5.18,5.46,12.90,20.78]

        # 	for i in range(len(box)):
        # 		box[i] *= 28.28

        # 	customer_info = tabula.read_pdf(path,pages = 1,area=box,output_format="json",stream=True)
        # 	customer_info = customer_info[0]['data']

        # 	for fields in customer_info:
        # 		##print(result)
        # 		for i,data in enumerate(fields):
        # 			if i == 0:
        # 				for key in keywords:
        # 					if key in data['text']:
        # 						ind = data['text'].index(key)
        # 						length = len(key)
        # 						result[key] = data['text'][ind+length+1:]
        # 						break
        # 			else:
        # 				try:
        # 					result[key] += data['text']
        # 				except:
        # 					pass
        # 	result['Account Summary'] = []
        # 	table = tabula.read_pdf(path,pages=x+1)
        # 	length = len(table[0].columns)
        # 	table[0].columns = list(range(length))
        # 	if table:
        # 		table = table[0].dropna(how='all')
        # 		if x == 0:
        # 			cols = table.iloc[0,:].values
        # 			table = table.iloc[1:,:]
        # 		table = table.reset_index()
        # 		for j in range(table.shape[0]):
        # 			res = {}
        # 			for k in range(length):
        # 				text = table[k][j]
        # 				if isinstance(text,str):
        # 					text = text.replace('\r',' ')
        # 				res[cols[k]] = text
        # 			result['Account Summary'].append(res)

        # 	# p#print.p#print(result)
        # 	#print(result)
        # 	finalResult.append(result)
        # return finalResult
    for bank in bankName:
        if os.path.exists(path):
            if bank == 'HDFC' and bank in extractedOutput:
                finalResult = hdfcBank(path)
            elif bank == 'ICICI' and bank in extractedOutput:
                finalResult = iciciBank(path)
            os.remove(path)
            # else:
            #     #print("Bank is not in the list.")

            # elif bank == 'AXIS' and bank in extractedOutput:
            # 	finalResult = axisBank(filepath)
            # elif bank == 'SBI' and bank in extractedOutput:
            # 	finalResult = sbiBank(filepath)
            # elif bank == 'KOTAK' and bank in extractedOutput:
            # 	finalResult = kotakBank(filepath)
            # elif bank == 'YES' and bank in extractedOutput:
            # 	finalResult = yesBank(filepath)
            # elif bank == 'CANARA' and bank in extractedOutput:
            # 	finalResult = canaraBank(filepath)

    return jsonify(finalResult), 200
