
# Authentication API Documentation

## Base URL
If running locally, the base URL is:
`http://<your-server-ip>:8000/api/auth`

Replace `<your-server-ip>` with your computer's IP address or `localhost` if testing on the same device.

---

### 1. Register
- **POST** `/register`
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "your_password",
    "name": "User Name"
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "data": {
      "id": 1,
      "email": "user@example.com",
      "name": "User Name"
    },
    "error": null
  }
  ```

---

### 2. Login
- **POST** `/login`
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "your_password"
  }
  ```
- **Note**: Email must be verified before login. Unverified users receive `403`.
- **Response**:
  ```json
  {
    "success": true,
    "data": {
      "access_token": "JWT_TOKEN",
      "token_type": "bearer"
    },
    "error": null
  }
  ```

---

### 3. Logout
- **POST** `/logout`
- **Headers**:  
  `Authorization: Bearer <JWT_TOKEN>`
- **Response**:
  ```json
  {
    "success": true,
    "data": true,
    "error": null
  }
  ```

---

### 4. Update Profile
- **PUT** `/profile`
- **Headers**:  
  `Authorization: Bearer <JWT_TOKEN>`
- **Request Body**:
  ```json
  {
    "name": "New Name"
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "data": {
      "id": 1,
      "email": "user@example.com",
      "name": "New Name"
    },
    "error": null
  }
  ```

---

### 5. Change Password
- **POST** `/change-password`
- **Headers**:  
  `Authorization: Bearer <JWT_TOKEN>`
- **Request Body**:
  ```json
  {
    "old_password": "current_password",
    "new_password": "new_password"
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "data": true,
    "error": null
  }
  ```

---

### 6. Forgot Password
- **POST** `/forgot-password`
- **Request Body**:
  ```json
  {
    "email": "user@example.com"
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "data": {
      "message": "If this email exists, reset instructions have been sent."
    },
    "error": null
  }
  ```

---

### 7. Verify Email
- **POST** `/verify-email`
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "otp": "123456"
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "data": true,
    "error": null
  }
  ```

---

### 8. Resend Verification Email
- **POST** `/resend-verification`
- **Request Body**:
  ```json
  {
    "email": "user@example.com"
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "data": {
      "message": "If this email exists and is unverified, a verification email has been sent."
    },
    "error": null
  }
  ```

- **Note**: The resend endpoint sends a fresh OTP code to email. Use that OTP with `/verify-email`.

---

### 9. Reset Password
- **POST** `/reset-password`
- **Request Body**:
  ```json
  {
    "token": "RESET_TOKEN",
    "new_password": "new_secure_password"
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "data": true,
    "error": null
  }
  ```

---

### 10. Remove Profile Image
- **DELETE** `/profile/image`
- **Headers**:  
  `Authorization: Bearer <JWT_TOKEN>`
- **Also available at**: `/api/profile/image`
- **Response**:
  ```json
  {
    "success": true,
    "data": {
      "id": 1,
      "email": "user@example.com",
      "name": "User Name",
      "profile_image": null,
      "bio": "My bio"
    },
    "error": null
  }
  ```

---

### 11. Clear Bio
- **DELETE** `/profile/bio`
- **Headers**:  
  `Authorization: Bearer <JWT_TOKEN>`
- **Also available at**: `/api/profile/bio`
- **Response**:
  ```json
  {
    "success": true,
    "data": {
      "id": 1,
      "email": "user@example.com",
      "name": "User Name",
      "profile_image": "/static/profile_images/user_1_profile.png",
      "bio": null
    },
    "error": null
  }
  ```

---

### 12. Delete Account
- **DELETE** `/`
- **Headers**:  
  `Authorization: Bearer <JWT_TOKEN>`
- **Response**:
  ```json
  {
    "success": true,
    "data": true,
    "error": null
  }
  ```

---


---

## Mobile Implementation Notes

- **Register/Login:**
  - Send POST requests with JSON bodies as shown above.
  - On successful login, store the `access_token` returned.

- **Authenticated Requests:**
  - For endpoints requiring authentication, add the following header:
    - `Authorization: Bearer <access_token>`
  - Replace `<access_token>` with the token received from login.

- **Error Handling:**
  - All responses include `success`, `data`, and `error` fields. Check `success` and handle errors accordingly.

- **Base URL:**
  - Use the full base URL for all requests from your mobile app.
  - Example: `http://192.168.1.10:8000/api/auth/register`

- **Content-Type:**
  - Always set `Content-Type: application/json` for POST/PUT requests.

---

All endpoints return a standardized response with `success`, `data`, and `error` fields. JWT authentication is required for protected routes.
