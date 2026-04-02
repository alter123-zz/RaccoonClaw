import { useEffect, useRef, useState, type ChangeEvent } from 'react';
import raccoonclawLogo from '../assets/raccoonclaw-logo.png';
import { api, type ChatAttachment, type ChatSessionDetail, type ChatSessionSummary } from '../api';
import { getSyncIndicator, useStore } from '../store';
import { formatBeijingDateTime } from '../time';

const LOCAL_PATH_RE = /(\/Users\/[^\s`]+(?:\.[A-Za-z0-9_-]+)?)/g;
const USER_AVATAR_KEY = 'raccoonclaw.chat.userAvatar';
const ASSISTANT_AVATAR_KEY = 'raccoonclaw.chat.assistantAvatar';

function extractLocalPaths(content: string): string[] {
  const matches = content.match(LOCAL_PATH_RE) || [];
  const cleaned = matches
    .map((item) => item.replace(/[),.!?]+$/g, '').trim())
    .filter((item) => item.includes('/'));
  return [...new Set(cleaned)];
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        resolve(reader.result);
        return;
      }
      reject(new Error('头像读取失败'));
    };
    reader.onerror = () => reject(new Error('头像读取失败'));
    reader.readAsDataURL(file);
  });
}

function avatarFallbackLabel(role: 'user' | 'assistant') {
  return role === 'user' ? '你' : '总';
}

function EmptyState() {
  return (
    <div className="chat-empty-state">
      <img src={raccoonclawLogo} alt="" className="chat-empty-logo" />
      <h1 className="chat-empty-brand">RaccoonClaw</h1>
      <p>7x24 小时，随时随地给总裁办安排工作。</p>
    </div>
  );
}

export default function ChatPanel() {
  const toast = useStore((s) => s.toast);
  const liveStatus = useStore((s) => s.liveStatus);
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [activeSession, setActiveSession] = useState<ChatSessionDetail | null>(null);
  const [draft, setDraft] = useState('');
  const [historyOpen, setHistoryOpen] = useState(false);
  const [loadingSession, setLoadingSession] = useState(false);
  const [loadingList, setLoadingList] = useState(false);
  const [sending, setSending] = useState(false);
  const [uploadingAttachments, setUploadingAttachments] = useState(false);
  const [removingAttachmentId, setRemovingAttachmentId] = useState<string | null>(null);
  const [openingPath, setOpeningPath] = useState<string | null>(null);
  const [userAvatar, setUserAvatar] = useState<string | null>(null);
  const [assistantAvatar, setAssistantAvatar] = useState<string | null>(null);
  const messageEndRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const userAvatarInputRef = useRef<HTMLInputElement | null>(null);
  const assistantAvatarInputRef = useRef<HTMLInputElement | null>(null);
  const syncIndicator = getSyncIndicator(liveStatus);
  const syncStatusText =
    syncIndicator.tone === 'ok'
      ? '链路状态：同步正常'
      : syncIndicator.tone === 'err'
        ? '链路状态：同步异常'
        : '链路状态：同步待确认';

  const loadSessions = async () => {
    setLoadingList(true);
    try {
      const data = await api.chatSessions();
      const nextSessions = data.sessions || [];
      setSessions(nextSessions);
    } catch {
      toast('对话列表加载失败', 'err');
    } finally {
      setLoadingList(false);
    }
  };

  const activateSession = async (sessionId: string) => {
    setLoadingSession(true);
    try {
      const data = await api.chatSession(sessionId);
      if (data.ok && data.session) {
        setActiveSessionId(sessionId);
        setActiveSession(data.session);
      } else {
        toast(data.error || '会话加载失败', 'err');
      }
    } catch {
      toast('会话加载失败', 'err');
    } finally {
      setLoadingSession(false);
    }
  };

  useEffect(() => {
    void loadSessions();
  }, []);

  useEffect(() => {
    if (!historyOpen) return;
    loadSessions();
  }, [historyOpen]);

  useEffect(() => {
    if (!activeSessionId) return;
    const timer = window.setInterval(() => {
      void activateSession(activeSessionId);
      void loadSessions();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [activeSessionId]);

  useEffect(() => {
    try {
      setUserAvatar(window.localStorage.getItem(USER_AVATAR_KEY));
      setAssistantAvatar(window.localStorage.getItem(ASSISTANT_AVATAR_KEY));
    } catch {
      setUserAvatar(null);
      setAssistantAvatar(null);
    }
  }, []);

  useEffect(() => {
    if (messageEndRef.current) {
      messageEndRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }, [activeSession?.messages?.length, sending]);

  const createSession = async (seedPrompt?: string) => {
    try {
      const data = await api.chatNewSession('');
      if (data.ok && data.session) {
        const created = data.session;
        setActiveSessionId(created.id);
        setActiveSession(created);
        setHistoryOpen(false);
        if (!seedPrompt) {
          setDraft('');
          toast('已新建对话', 'ok');
        }
        if (seedPrompt) {
          setDraft(seedPrompt);
        }
      } else {
        toast(data.error || '新建会话失败', 'err');
      }
    } catch {
      toast('新建会话失败', 'err');
    }
  };

  const ensureSession = async () => {
    if (activeSessionId && activeSession) {
      return { sessionId: activeSessionId, session: activeSession };
    }
    const created = await api.chatNewSession('');
    if (!created.ok || !created.session) {
      throw new Error(created.error || '新建会话失败');
    }
    setActiveSessionId(created.session.id);
    setActiveSession(created.session);
    setHistoryOpen(false);
    return { sessionId: created.session.id, session: created.session };
  };

  const handlePickAttachments = () => {
    if (uploadingAttachments || sending) return;
    fileInputRef.current?.click();
  };

  const handlePickAvatar = (role: 'user' | 'assistant') => {
    if (role === 'user') {
      userAvatarInputRef.current?.click();
      return;
    }
    assistantAvatarInputRef.current?.click();
  };

  const handleAvatarSelected = async (role: 'user' | 'assistant', event: ChangeEvent<HTMLInputElement>) => {
    const picked = event.target.files?.[0];
    event.target.value = '';
    if (!picked) return;

    try {
      const dataUrl = await readFileAsDataUrl(picked);
      if (role === 'user') {
        setUserAvatar(dataUrl);
        window.localStorage.setItem(USER_AVATAR_KEY, dataUrl);
        toast('已更新你的头像', 'ok');
        return;
      }
      setAssistantAvatar(dataUrl);
      window.localStorage.setItem(ASSISTANT_AVATAR_KEY, dataUrl);
      toast('已更新总裁办头像', 'ok');
    } catch (error) {
      toast(error instanceof Error ? error.message : '头像更新失败', 'err');
    }
  };

  const renderAvatar = (role: 'user' | 'assistant') => {
    const src = role === 'user' ? userAvatar : assistantAvatar || raccoonclawLogo;
    const label = role === 'user' ? '你' : '总裁办';
    return (
      <button
        type="button"
        className={`chat-message-avatar ${role}`}
        onClick={() => handlePickAvatar(role)}
        title={role === 'user' ? '点击更换你的头像' : '点击更换总裁办头像'}
        aria-label={role === 'user' ? '更换你的头像' : '更换总裁办头像'}
      >
        {src ? (
          <img src={src} alt={label} />
        ) : (
          <span className="chat-message-avatar-fallback">{avatarFallbackLabel(role)}</span>
        )}
      </button>
    );
  };

  const handleFilesSelected = async (event: ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(event.target.files || []);
    event.target.value = '';
    if (!picked.length) return;

    setUploadingAttachments(true);
    try {
      const { sessionId } = await ensureSession();
      const data = await api.chatUploadAttachments(sessionId, picked);
      if (data.ok && data.session) {
        setActiveSession(data.session);
        await loadSessions();
        toast(`已上传 ${picked.length} 个附件`, 'ok');
      } else {
        toast(data.error || data.message || '附件上传失败', 'err');
      }
    } catch (error) {
      toast(error instanceof Error ? error.message : '附件上传失败', 'err');
    } finally {
      setUploadingAttachments(false);
    }
  };

  const handleRemoveAttachment = async (attachmentId: string) => {
    if (!activeSessionId || removingAttachmentId || uploadingAttachments || sending) return;
    setRemovingAttachmentId(attachmentId);
    try {
      const data = await api.chatRemoveAttachment(activeSessionId, attachmentId);
      if (data.ok && data.session) {
        setActiveSession(data.session);
        await loadSessions();
      } else {
        toast(data.error || data.message || '附件删除失败', 'err');
      }
    } catch {
      toast('附件删除失败', 'err');
    } finally {
      setRemovingAttachmentId(null);
    }
  };

  const send = async () => {
    const content = draft.trim();
    const pendingAttachments = activeSession?.pendingAttachments || [];
    if ((!content && !pendingAttachments.length) || sending || uploadingAttachments) return;

    let sessionId = activeSessionId;
    let current = activeSession;
    if (!sessionId) {
      try {
        const created = await api.chatNewSession('');
        if (!created.ok || !created.session) {
          toast(created.error || '新建会话失败', 'err');
          return;
        }
        sessionId = created.session.id;
        current = created.session;
        setActiveSessionId(sessionId);
        setActiveSession(created.session);
        setHistoryOpen(false);
      } catch {
        toast('新建会话失败', 'err');
        return;
      }
    }

    const optimistic: ChatSessionDetail = current
      ? {
          ...current,
          updatedAt: new Date().toISOString(),
          messages: [
            ...current.messages,
            {
              id: `draft-${Date.now()}`,
              role: 'user',
              content,
              createdAt: new Date().toISOString(),
              attachments: pendingAttachments,
            },
          ],
          pendingAttachments: [],
        }
      : {
          id: sessionId!,
          title: '新对话',
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          lastMessage: '',
          messageCount: 1,
          messages: [
            {
              id: `draft-${Date.now()}`,
              role: 'user',
              content,
              createdAt: new Date().toISOString(),
              attachments: pendingAttachments,
            },
          ],
          pendingAttachments: [],
        };

    setActiveSession(optimistic);
    setDraft('');
    setSending(true);
    try {
      const data = await api.chatSend(sessionId!, content);
      if (data.ok && data.session) {
        setActiveSession(data.session);
        await loadSessions();
      } else {
        toast(data.error || data.message || '发送失败', 'err');
        if (sessionId) await activateSession(sessionId);
      }
    } catch {
      toast('发送失败', 'err');
      if (sessionId) await activateSession(sessionId);
    } finally {
      setSending(false);
    }
  };

  const handleOpenPath = async (path: string) => {
    if (!path || openingPath) return;
    setOpeningPath(path);
    try {
      const data = await api.openPath(path);
      if (!data.ok) {
        toast(data.error || data.message || '打开失败', 'err');
      }
    } catch {
      toast('打开失败', 'err');
    } finally {
      setOpeningPath(null);
    }
  };

  return (
    <div className="chat-shell chat-shell-single">
      <section className="chat-main">
        <div className="chat-main-topbar">
          <div className={`chat-link-status ${syncIndicator.tone}`}>
            <span className="chat-link-status-dot" aria-hidden="true" />
            <span className="chat-link-status-value">{syncStatusText}</span>
          </div>
          <div className="chat-topbar-actions">
            <button type="button" className="chat-topbar-btn" onClick={() => createSession()}>
              新对话
            </button>
            <button
              type="button"
              className="chat-topbar-btn"
              onClick={() => setHistoryOpen((value) => !value)}
            >
              {historyOpen ? '收起历史对话' : '展开历史对话'}
            </button>
            <span className="chat-topbar-title">
              {activeSession && activeSession.messages.length ? activeSession.title : ''}
            </span>
          </div>
        </div>

        <div className="chat-main-body">
          {!activeSession || !activeSession.messages.length ? (
            <EmptyState />
          ) : (
            <div className="chat-message-list">
              {activeSession.messages.map((message) => (
                <div key={message.id} className={`chat-message-row ${message.role}`}>
                  {message.role === 'assistant' ? renderAvatar('assistant') : null}
                  <div className={`chat-message-stack ${message.role}`}>
                    <div className={`chat-message-name ${message.role}`}>{message.role === 'user' ? '你' : '总裁办'}</div>
                    <div className={`chat-message-bubble ${message.role} ${message.error ? 'error' : ''}`}>
                      {message.attachments?.length ? (
                        <div className="chat-attachment-list">
                          {message.attachments.map((attachment) => (
                            <div key={attachment.id} className="chat-attachment-item">
                              <span className="chat-attachment-kind">{attachment.kind === 'image' ? '🖼️' : '📄'}</span>
                              <span className="chat-attachment-name">{attachment.name}</span>
                            </div>
                          ))}
                        </div>
                      ) : null}
                      <div className="chat-message-content">{message.content}</div>
                      {message.role === 'assistant' && extractLocalPaths(message.content).length ? (
                        <div className="chat-message-actions">
                          {extractLocalPaths(message.content).map((path) => (
                            <button
                              key={path}
                              type="button"
                              className="chat-open-path-btn"
                              onClick={() => handleOpenPath(path)}
                              disabled={openingPath === path}
                            >
                              {openingPath === path ? '打开中…' : '📂 直接打开'}
                            </button>
                          ))}
                        </div>
                      ) : null}
                    </div>
                    <div className={`chat-message-time ${message.role}`}>
                      {formatBeijingDateTime(message.createdAt, { includeSeconds: false })}
                    </div>
                  </div>
                  {message.role === 'user' ? renderAvatar('user') : null}
                </div>
              ))}
              {loadingSession && <div className="chat-session-empty">加载会话中…</div>}
              <div ref={messageEndRef} />
            </div>
          )}
        </div>

        <div className="chat-input-shell">
          <div className="chat-input-card">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="image/*,.pdf,.txt,.md,.markdown,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.csv,.json"
              className="chat-file-input"
              onChange={handleFilesSelected}
            />
            <input
              ref={userAvatarInputRef}
              type="file"
              accept="image/*"
              className="chat-file-input"
              onChange={(event) => handleAvatarSelected('user', event)}
            />
            <input
              ref={assistantAvatarInputRef}
              type="file"
              accept="image/*"
              className="chat-file-input"
              onChange={(event) => handleAvatarSelected('assistant', event)}
            />
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="可以描述任务或提问任何问题"
              rows={4}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
            />
            {activeSession?.pendingAttachments?.length ? (
              <div className="chat-pending-attachments">
                {activeSession.pendingAttachments.map((attachment: ChatAttachment) => (
                  <div key={attachment.id} className="chat-pending-attachment">
                    <span>{attachment.kind === 'image' ? '🖼️' : '📄'}</span>
                    <span>{attachment.name}</span>
                    <button
                      type="button"
                      className="chat-pending-attachment-remove"
                      onClick={() => handleRemoveAttachment(attachment.id)}
                      disabled={removingAttachmentId === attachment.id}
                      aria-label={`删除附件 ${attachment.name}`}
                    >
                      {removingAttachmentId === attachment.id ? '…' : '×'}
                    </button>
                  </div>
                ))}
              </div>
            ) : null}
            <div className="chat-input-footer">
              <div className="chat-input-actions">
                <button
                  type="button"
                  className="chat-attach-btn"
                  onClick={handlePickAttachments}
                  disabled={uploadingAttachments || sending}
                  aria-label={uploadingAttachments ? '上传中' : '上传图片或文档'}
                  title={uploadingAttachments ? '上传中' : '上传图片或文档'}
                >
                  {uploadingAttachments ? (
                    <span aria-hidden="true">…</span>
                  ) : (
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path
                        d="M8.5 12.5 13.8 7.2a3 3 0 1 1 4.2 4.2l-7.1 7.1a5 5 0 0 1-7.1-7.1l8-8"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  )}
                </button>
                <div className="chat-input-hint">当前只连接总裁办，非流式回复。</div>
              </div>
              <button
                type="button"
                className="chat-send-btn"
                onClick={send}
                disabled={sending || uploadingAttachments || (!draft.trim() && !(activeSession?.pendingAttachments || []).length)}
              >
                {sending ? '发送中…' : '发送'}
              </button>
            </div>
          </div>
        </div>

        {historyOpen ? (
          <aside className="chat-history-drawer">
            <div className="chat-history-drawer-head">
              <strong>历史对话</strong>
              <button type="button" className="chat-history-close" onClick={() => setHistoryOpen(false)}>
                ×
              </button>
            </div>
            <div className="chat-session-list chat-session-list-drawer">
              {loadingList ? (
                <div className="chat-session-empty">加载中…</div>
              ) : sessions.length ? (
                sessions.map((session) => (
                  <button
                    key={session.id}
                    type="button"
                    className={`chat-session-item ${activeSessionId === session.id ? 'active' : ''}`}
                    onClick={() => {
                      setHistoryOpen(false);
                      void activateSession(session.id);
                    }}
                  >
                    <div className="chat-session-title">{session.title || '新对话'}</div>
                    <div className="chat-session-preview">{session.lastMessage || '暂无消息'}</div>
                    <div className="chat-session-time">
                      {session.updatedAt ? formatBeijingDateTime(session.updatedAt, { includeSeconds: false }) : ''}
                    </div>
                  </button>
                ))
              ) : (
                <div className="chat-session-empty">暂无历史对话</div>
              )}
            </div>
          </aside>
        ) : null}
      </section>
    </div>
  );
}
