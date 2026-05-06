import request from "../utils/request.js";

export function authLogin(body) {
  return request.post("/api/auth/login", body);
}

export function authRegister(body) {
  return request.post("/api/auth/register", body);
}

export function authMe() {
  return request.get("/api/auth/me");
}

export function authListUsers() {
  return request.get("/api/auth/users");
}

export function authUpdateUserLevel(userId, level) {
  return request.patch(`/api/auth/users/${userId}/level`, { level });
}

export function authDeleteUser(userId) {
  return request.delete(`/api/auth/users/${userId}`);
}
