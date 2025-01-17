import os
from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId
import face_recognition
from PIL import Image

app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb+srv://indeseg:indeseg@indeseg.gev35.mongodb.net/indeseg"
mongo = PyMongo(app)

users = mongo.db.users

# Crear carpeta para almacenar imágenes si no existe
if not os.path.exists("user_images"):
    os.makedirs("user_images")

"""
Registra un nuevo usuario con un nombre de usuario, contraseña e imagen de perfil.
Este endpoint maneja el registro de un nuevo usuario aceptando una solicitud POST
con datos de formulario que contienen un nombre de usuario, contraseña y un archivo de imagen. Realiza
los siguientes pasos:
1. Verifica si el nombre de usuario ya existe en la base de datos.
2. Hashea la contraseña proporcionada.
3. Guarda la imagen de perfil del usuario en el sistema de archivos.
4. Rota la imagen si es necesario.
5. Intenta detectar un rostro en la imagen usando reconocimiento facial.
6. Si no se detecta un rostro o ocurre un error, se eliminan la imagen y el registro del usuario.
7. Si tiene éxito, devuelve un mensaje de éxito con el ID del usuario.
Devuelve:
    Respuesta JSON que indica el éxito o fracaso del proceso de registro.
    En caso de éxito: {"message": "Usuario registrado exitosamente", "user_id": str(user_id)}
    En caso de fallo: {"error": "mensaje de error"}
Lanza:
    Error 400 si el nombre de usuario ya está registrado o no se detecta un rostro en la imagen.
    Error 500 si ocurre un error al procesar la imagen.
"""
@app.route("/register", methods=["POST"])
def register():
    data = request.form  # Usar 'form' para datos y archivos enviados
    username = data.get("username")
    password = data.get("password")
    image = request.files["image"]

    if users.find_one({"username": username}):
        return jsonify({"error": "Usuario ya registrado"}), 400

    hashed_password = generate_password_hash(password)
    user_id = users.insert_one({
        "username": username,
        "password": hashed_password
    }).inserted_id

    # Guardar la imagen en el sistema de archivos
    image_path = f"user_images/{user_id}.jpg"
    image.save(image_path)

    image_pil = Image.open(image_path).convert("RGB")
    # girar la imagen si es necesario
    image_pil = image_pil.rotate(90)
    
    image_pil.save(image_path)

    registered_image = face_recognition.load_image_file(image_path)

    try:
        registered_encoding = face_recognition.face_encodings(registered_image, model="hog", num_jitters=1)
        if not registered_encoding:
            os.remove(image_path)
            users.delete_one({"_id": ObjectId(user_id)})
            return jsonify({"error": "No se detectó un rostro en la imagen"}), 400
    except Exception as e:
        os.remove(image_path)
        users.delete_one({"_id": ObjectId(user_id)})
        return jsonify({"error": f"Ocurrió un error al procesar la imagen: {str(e)}"}), 500
    
    print(registered_encoding)
    return jsonify({"message": "Usuario registrado exitosamente", "user_id": str(user_id)})


"""
Maneja el proceso de inicio de sesión para los usuarios.
Esta función está mapeada a la ruta "/login" y acepta solicitudes POST. Realiza los siguientes pasos:
1. Recupera el nombre de usuario, contraseña e imagen de inicio de sesión de la solicitud.
2. Verifica si el usuario existe y si la contraseña proporcionada es correcta.
3. Carga la imagen registrada del usuario desde el sistema de archivos.
4. Convierte tanto la imagen registrada como la imagen de inicio de sesión a arrays y las compara usando reconocimiento facial.
5. Elimina el archivo de imagen de inicio de sesión temporal.
6. Devuelve una respuesta JSON que indica si el inicio de sesión fue exitoso o si hubo algún error.
Devuelve:
    Respuesta JSON que indica el resultado del intento de inicio de sesión.
    - 200: {"message": "Inicio de sesión exitoso"} si el inicio de sesión es exitoso.
    - 401: {"error": "No coinciden las imágenes"} si las imágenes no coinciden.
    - 402: {"error": "Credenciales inválidas"} si el nombre de usuario o la contraseña son incorrectos.
    - 404: {"error": "Imagen registrada no encontrada"} si la imagen registrada no se encuentra.
    - 400: {"error": "No se detectaron rostros en las imágenes"} si no se detectan rostros en las imágenes.
"""
@app.route("/login", methods=["POST"])
def login():
    data = request.form
    username = data.get("username")
    password = data.get("password")
    login_image = request.files["image"]

    user = users.find_one({"username": username})
    if not user or not check_password_hash(user["password"], password):
        return jsonify({"error": "Credenciales inválidas"}), 402

    # Cargar la imagen registrada del usuario
    registered_image_path = f"user_images/{user['_id']}.jpg"
    if not os.path.exists(registered_image_path):
        return jsonify({"error": "Imagen registrada no encontrada"}), 404

    # Convertir ambas imágenes a arrays y compararlas
    registered_image = face_recognition.load_image_file(registered_image_path)
    # login_image_data = Image.open(io.BytesIO(login_image.read())).convert("RGB")
    image_path = f"user_images/{user['_id']}00.jpg"
    login_image.save(image_path)
    image_pil = Image.open(image_path).convert("RGB")
    image_pil = image_pil.rotate(90)
    image_pil.save(image_path)
    login_image = face_recognition.load_image_file(image_path)

    registered_encoding = face_recognition.face_encodings(registered_image)
    login_encoding = face_recognition.face_encodings(login_image)

    print(registered_encoding)
    print(login_encoding)

    # eliminar la imagen temporal
    os.remove(image_path)
    if registered_encoding and login_encoding:
        matches = face_recognition.compare_faces([registered_encoding[0]], login_encoding[0])
        if matches[0]:
            return jsonify({"message": "Inicio de sesión exitoso"})
        else:
            return jsonify({"error": "No coinciden las imágenes"}), 401
    else:
        return jsonify({"error": "No se detectaron rostros en las imágenes"}), 400

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
