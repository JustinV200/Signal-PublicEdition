// Public entry point of the api package: the only import path other packages use.
export { openCameraStream } from "./camera/stream";
export type { CameraHandlers } from "./camera/stream";
export {
  getDevices,
  getState,
  login,
  pickModel,
  sendAction,
  sendText,
  setAway,
  UnauthorizedError,
} from "./client";
export { connectEvents, STALL_MS } from "./events";
export type { EventHandlers, EventStream } from "./events";
export { createMjpegParser } from "./camera/mjpeg";
export type { MjpegParser } from "./camera/mjpeg";
export * from "./setup";
export { createSseParser } from "./sse";
export type { SseEvent, SseParser } from "./sse";
export { getToken } from "./token";
export type {
  ActionArgs,
  ActionName,
  AwayInfo,
  AwayState,
  BoardSave,
  BoardState,
  Delivery,
  DeliveryStatus,
  DeviceRow,
  DevicesPayload,
  DeviceState,
  Message,
  MessageKind,
  MessageRole,
  ModelChoices,
  ModelField,
  ModelPick,
  ModelsState,
  ModelTarget,
  Note,
  ServerEvent,
  ServerState,
  TaskInfo,
  TasksPayload,
  TaskStatus,
  TurnStateName,
  TurnStatus,
  UsageInfo,
  UsageWindow,
  VoiceEvent,
  VoiceEventKind,
  VoicePhase,
  VoiceState,
} from "./types";
