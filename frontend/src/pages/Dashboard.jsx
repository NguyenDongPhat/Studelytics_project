import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Bot,
    CalendarDays,
    ChevronLeft,
    ChevronRight,
    Eye,
    FileText,
    FileUp,
    Filter,
    Globe2,
    Grid3X3,
    Hash,
    LayoutList,
    Lock,
    MessageCircle,
    Plus,
    Search,
    Share2,
    Tag,
    Trash2,
    UploadCloud,
    UserRound,
    X
} from 'lucide-react';
import '../assets/css/dashboard.css';

const Dashboard = () => {
    const navigate = useNavigate();
    const fileInputRef = useRef(null);
    const API_URL = import.meta.env.VITE_API_URL;

    const [data, setData] = useState({ stats: {}, documents: [] });
    const [sharedDocs, setSharedDocs] = useState([]);
    const [viewMode, setViewMode] = useState('view-grid');

    const [searchQuery, setSearchQuery] = useState('');
    const [sortValue, setSortValue] = useState('newest');
    const [filterVisibility, setFilterVisibility] = useState('all');

    const [isModalOpen, setIsModalOpen] = useState(false);
    const [selectedFile, setSelectedFile] = useState(null);
    const [uploadTitle, setUploadTitle] = useState('');
    const [uploadDescription, setUploadDescription] = useState('');
    const [uploadCategory, setUploadCategory] = useState('khác');
    const [uploadVisibility, setUploadVisibility] = useState('private');
    const [uploadTags, setUploadTags] = useState([]);
    const [tagInput, setTagInput] = useState('');
    const [isUploading, setIsUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [page, setPage] = useState(1);
    const [pagination, setPagination] = useState({
        page: 1,
        limit: 12,
        total: 0,
        total_pages: 1
    });

    const fetchDashboardData = async (pageNumber = page) => {
        try {
            const [dashboardRes, sharedRes] = await Promise.all([
                fetch(`${API_URL}/api/dashboard?page=${pageNumber}&limit=12`, {
                    credentials: 'include',
                    cache: 'no-store'
                }),
                fetch(`${API_URL}/api/shared-with-me`, {
                    credentials: 'include',
                    cache: 'no-store'
                })
            ]);

            let sharedItems = [];

            if (sharedRes.ok) {
                const sharedResult = await sharedRes.json();
                sharedItems = Array.isArray(sharedResult)
                    ? sharedResult
                    : (sharedResult.items || sharedResult.shared_documents || []);
            }

            setSharedDocs(sharedItems);

            if (dashboardRes.ok) {
                const result = await dashboardRes.json();
                const sharedFromDashboard = result.shared_documents || sharedItems;

                setData({
                    stats: {
                        ...(result.stats || { total: 0, public: 0, private: 0 }),
                        shared_with_me: sharedFromDashboard.length
                    },
                    documents: result.my_documents || []
                });

                if (result.shared_documents) {
                    setSharedDocs(result.shared_documents);
                }

                setPagination(
                    result.pagination || {
                        page: pageNumber,
                        limit: 12,
                        total: result.my_documents?.length || 0,
                        total_pages: 1
                    }
                );
            }
        } catch (error) {
            console.error('Lỗi lấy dữ liệu:', error);
        }
    };

    useEffect(() => {
        fetch(`${API_URL}/api/users/me`, {
            credentials: 'include',
            cache: 'no-store'
        })
            .then(res => {
                if (res.status === 401) {
                    alert('Bạn cần đăng nhập để sử dụng Dashboard cá nhân!');
                    navigate('/login');
                }
            })
            .catch(() => {});

        fetchDashboardData(page);
    }, [page]);

    const normalizeTags = (tags) => {
        if (!tags) return [];
        if (Array.isArray(tags)) return tags.filter(Boolean);

        if (typeof tags === 'string') {
            return tags
                .split(',')
                .map(tag => tag.trim())
                .filter(Boolean);
        }

        return [];
    };

    const handleTagKeyDown = (e) => {
        if (e.key === 'Enter' || e.key === ',') {
            e.preventDefault();

            const newTag = tagInput.trim().toLowerCase().replace(/,/g, '');
            if (newTag && !uploadTags.includes(newTag)) {
                setUploadTags([...uploadTags, newTag]);
            }

            setTagInput('');
        }
    };

    const removeTag = (tagToRemove) => {
        setUploadTags(uploadTags.filter(tag => tag !== tagToRemove));
    };

    const filterAndSortDocuments = (items) => {
        const searchLower = searchQuery.trim().toLowerCase();

        const docs = [...items].filter(doc => {
            const tags = normalizeTags(doc.tags);
            const title = doc.title || '';
            const description = doc.description || '';
            const owner = doc.shared_by_username || doc.owner_username || '';

            const matchSearch = !searchLower ||
                title.toLowerCase().includes(searchLower) ||
                description.toLowerCase().includes(searchLower) ||
                owner.toLowerCase().includes(searchLower) ||
                tags.some(tag => tag.toLowerCase().includes(searchLower));

            const matchVis = filterVisibility === 'all' || doc.visibility === filterVisibility;
            return matchSearch && matchVis;
        });

        docs.sort((a, b) => {
            if (sortValue === 'newest') return (b.id || 0) - (a.id || 0);
            if (sortValue === 'oldest') return (a.id || 0) - (b.id || 0);
            if (sortValue === 'az') return (a.title || '').localeCompare(b.title || '');
            if (sortValue === 'za') return (b.title || '').localeCompare(a.title || '');
            return 0;
        });

        return docs;
    };

    const filteredDocs = useMemo(() => {
        return filterAndSortDocuments(data.documents);
    }, [data.documents, searchQuery, filterVisibility, sortValue]);

    const filteredSharedDocs = useMemo(() => {
        return filterAndSortDocuments(sharedDocs);
    }, [sharedDocs, searchQuery, filterVisibility, sortValue]);

    const updateVisibility = async (docId, newVisibility) => {
        try {
            const res = await fetch(`${API_URL}/api/documents/${docId}/visibility`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ visibility: newVisibility }),
                credentials: 'include'
            });

            if (res.ok) fetchDashboardData();
        } catch (error) {
            alert('Lỗi khi cập nhật trạng thái!');
        }
    };

    const deleteDoc = async (docId) => {
        if (!window.confirm('Bạn có chắc chắn muốn xóa tài liệu này? Toàn bộ lịch sử chat sẽ bị xóa.')) return;

        try {
            const res = await fetch(`${API_URL}/api/documents/${docId}`, {
                method: 'DELETE',
                credentials: 'include'
            });

            if (res.ok) fetchDashboardData();
        } catch (error) {
            alert('Lỗi kết nối mạng!');
        }
    };

    const handleFileChange = (e) => {
        if (e.target.files.length > 0) {
            const file = e.target.files[0];
            setSelectedFile(file);
            setUploadTitle(file.name.replace(/\.[^/.]+$/, ''));
        }
    };

    const closeUploadModal = () => {
        if (isUploading) return;

        setIsModalOpen(false);
        setSelectedFile(null);
        setUploadTitle('');
        setUploadDescription('');
        setUploadCategory('khác');
        setUploadVisibility('private');
        setUploadTags([]);
        setTagInput('');
        setUploadProgress(0);
    };

    const handleUploadSubmit = async (e) => {
        e.preventDefault();
        if (!selectedFile) return;

        if (selectedFile.type !== 'application/pdf' && !selectedFile.name.toLowerCase().endsWith('.pdf')) {
            alert('Vui lòng chọn file PDF.');
            return;
        }

        if (selectedFile.size > 50 * 1024 * 1024) {
            alert('File quá lớn. Dung lượng tối đa là 50MB.');
            return;
        }

        setIsUploading(true);
        setUploadProgress(0);

        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('title', uploadTitle);
        formData.append('description', uploadDescription);
        formData.append('category', uploadCategory);
        formData.append('visibility', uploadVisibility);
        formData.append('tags', uploadTags.join(','));

        const xhr = new XMLHttpRequest();
        xhr.open('POST', `${API_URL}/api/upload`);
        xhr.withCredentials = true;

        xhr.upload.onprogress = (event) => {
            if (event.lengthComputable) {
                setUploadProgress(Math.round((event.loaded / event.total) * 100));
            }
        };

        xhr.onload = () => {
            setIsUploading(false);

            if (xhr.status >= 200 && xhr.status < 300) {
                closeUploadModal();
                setPage(1);
                fetchDashboardData(1);
            } else {
                let message = 'Lỗi tải lên!';
                try {
                    message = JSON.parse(xhr.responseText).detail || message;
                } catch (_) {}
                alert(message);
            }
        };

        xhr.onerror = () => {
            setIsUploading(false);
            alert('Lỗi kết nối!');
        };

        xhr.send(formData);
    };

    const formatDate = (date) => {
        return date ? new Date(date).toLocaleDateString('vi-VN') : 'Mới đây';
    };

    const getPermissionLabel = (permission) => {
        return permission === 'edit' ? 'Có thể sửa' : 'Chỉ xem';
    };

    const renderDocumentCard = (doc, options = {}) => {
        const tags = normalizeTags(doc.tags);
        const isPublic = doc.visibility === 'public';
        const isShared = options.shared || doc.is_shared || doc.source === 'shared';

        return (
            <div key={`${isShared ? 'shared' : 'own'}-${doc.id}`} className={`card doc-card ${isShared ? 'shared-doc-card' : ''}`}>
                <div className="doc-main">
                    <div className="doc-icon">
                        {isShared ? <Share2 size={24} /> : <FileText size={24} />}
                    </div>

                    <div className="doc-heading">
                        <h3 className="doc-title" title={doc.title}>{doc.title}</h3>
                        <div className="doc-date">
                            <CalendarDays size={14} />
                            {formatDate(doc.upload_date || doc.created_at)}
                        </div>
                    </div>
                </div>

                {isShared && (
                    <div className="shared-meta-box">
                        <span className="shared-badge">
                            <UserRound size={13} />
                            Được chia sẻ bởi {doc.shared_by_username || doc.owner_username || 'Ẩn danh'}
                        </span>
                        <span className="permission-badge">
                            {getPermissionLabel(doc.permission)}
                        </span>
                    </div>
                )}

                <div className="doc-info">
                    <p className="doc-description">
                        {doc.description || 'Chưa có mô tả cho tài liệu này.'}
                    </p>

                    {tags.length > 0 && (
                        <div className="doc-tags">
                            {tags.map(tag => (
                                <button
                                    type="button"
                                    key={tag}
                                    className="doc-tag"
                                    onClick={() => setSearchQuery(tag)}
                                >
                                    <Hash size={12} />
                                    {tag}
                                </button>
                            ))}
                        </div>
                    )}
                </div>

                <div className="doc-actions">
                    {!isShared && (
                        <div className={`visibility-wrapper ${isPublic ? 'public' : 'private'}`}>
                            {isPublic ? <Globe2 size={15} /> : <Lock size={15} />}
                            <select
                                className="visibility-select"
                                value={doc.visibility}
                                onChange={(e) => updateVisibility(doc.id, e.target.value)}
                                title="Đổi chế độ tài liệu"
                            >
                                <option value="private">Private</option>
                                <option value="public">Public</option>
                            </select>
                        </div>
                    )}

                    {isShared && (
                        <div className="visibility-wrapper shared-readonly">
                            <Share2 size={15} />
                            <span>Được chia sẻ</span>
                        </div>
                    )}

                    <button
                        className="btn-outline action-btn"
                        onClick={() => navigate(`/document/${doc.id}`)}
                    >
                        <Eye size={15} />
                        Chi tiết
                    </button>

                    <button
                        className="btn-outline action-btn"
                        onClick={() => navigate(`/chat?doc_id=${doc.id}`)}
                    >
                        <MessageCircle size={15} />
                        Hỏi AI
                    </button>

                    {!isShared && (
                        <button
                            className="btn-outline delete-btn"
                            onClick={() => deleteDoc(doc.id)}
                            title="Xóa tài liệu"
                        >
                            <Trash2 size={15} />
                        </button>
                    )}
                </div>
            </div>
        );
    };

    return (
        <>
            <div className="dashboard-page">
                <div className="dashboard-header">
                    <div>
                        <h2>Không gian làm việc của tôi</h2>
                        <span>Quản lý tài liệu, tag và hỏi AI trên từng tài liệu.</span>
                    </div>

                    <div className="header-buttons">
                        <button className="btn-outline" onClick={() => navigate('/public-documents')}>
                            <Globe2 size={16} />
                            Khám phá cộng đồng
                        </button>

                        <button className="btn-main" onClick={() => setIsModalOpen(true)}>
                            <Plus size={17} />
                            Tải lên tài liệu
                        </button>
                    </div>
                </div>

                <div className="stats">
                    <div className="stat-card">
                        <div className="stat-icon">
                            <FileText size={21} />
                        </div>
                        <div>
                            <h3>Tổng số tài liệu</h3>
                            <p>{data.stats.total || 0}</p>
                        </div>
                    </div>

                    <div className="stat-card">
                        <div className="stat-icon">
                            <Globe2 size={21} />
                        </div>
                        <div>
                            <h3>Đang chia sẻ</h3>
                            <p>{data.stats.public || 0}</p>
                        </div>
                    </div>

                    <div className="stat-card">
                        <div className="stat-icon">
                            <Lock size={21} />
                        </div>
                        <div>
                            <h3>Riêng tư</h3>
                            <p>{data.stats.private || 0}</p>
                        </div>
                    </div>

                    <div className="stat-card">
                        <div className="stat-icon">
                            <Share2 size={21} />
                        </div>
                        <div>
                            <h3>Được chia sẻ</h3>
                            <p>{data.stats.shared_with_me || sharedDocs.length || 0}</p>
                        </div>
                    </div>
                </div>

                <div className="toolbar">
                    <div className="toolbar-group">
                        <div className="search-field">
                            <Search size={16} />
                            <input
                                type="text"
                                placeholder="Tìm tài liệu, mô tả hoặc tag..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                            />
                        </div>

                        <div className="select-field">
                            <select value={sortValue} onChange={(e) => setSortValue(e.target.value)}>
                                <option value="newest">Mới nhất</option>
                                <option value="oldest">Cũ nhất</option>
                                <option value="az">Tên A-Z</option>
                                <option value="za">Tên Z-A</option>
                            </select>
                        </div>

                        <div className="select-field">
                            <Filter size={15} />
                            <select value={filterVisibility} onChange={(e) => setFilterVisibility(e.target.value)}>
                                <option value="all">Tất cả trạng thái</option>
                                <option value="public">Đang Public</option>
                                <option value="private">Đang Private</option>
                            </select>
                        </div>
                    </div>

                    <div className="view-toggles">
                        <button
                            type="button"
                            className={viewMode === 'view-grid' ? 'active' : ''}
                            onClick={() => setViewMode('view-grid')}
                        >
                            <Grid3X3 size={15} />
                            Lưới
                        </button>

                        <button
                            type="button"
                            className={viewMode === 'view-list' ? 'active' : ''}
                            onClick={() => setViewMode('view-list')}
                        >
                            <LayoutList size={15} />
                            Danh sách
                        </button>
                    </div>
                </div>

                <div className="dashboard-section-head">
                    <div>
                        <h3>Tài liệu của tôi</h3>
                        <span>{filteredDocs.length} tài liệu phù hợp</span>
                    </div>
                </div>

                <div className={`grid-container ${viewMode}`}>
                    {filteredDocs.length > 0 ? (
                        filteredDocs.map(doc => renderDocumentCard(doc))
                    ) : (
                        <div className="empty-state">
                            <FileText size={36} />
                            <h3>{searchQuery ? 'Không tìm thấy tài liệu' : 'Bạn chưa có tài liệu nào'}</h3>
                            <p>
                                {searchQuery
                                    ? 'Thử đổi từ khóa, tag hoặc bộ lọc trạng thái.'
                                    : 'Tải lên tài liệu PDF đầu tiên để bắt đầu hỏi AI.'}
                            </p>
                        </div>
                    )}
                </div>

                {pagination.total_pages > 1 && (
                    <div className="pagination-bar">
                        <button
                            className="btn-outline"
                            disabled={page <= 1}
                            onClick={() => setPage(prev => Math.max(1, prev - 1))}
                        >
                            <ChevronLeft size={15} />
                            Trước
                        </button>

                        <span>Trang {pagination.page} / {pagination.total_pages} · {pagination.total} tài liệu</span>

                        <button
                            className="btn-outline"
                            disabled={page >= pagination.total_pages}
                            onClick={() => setPage(prev => Math.min(pagination.total_pages, prev + 1))}
                        >
                            Sau
                            <ChevronRight size={15} />
                        </button>
                    </div>
                )}

                <div className="dashboard-section-head shared-section-head">
                    <div>
                        <h3>Tài liệu được chia sẻ với tôi</h3>
                        <span>Các tài liệu người khác chia sẻ vào tài khoản của bạn.</span>
                    </div>
                    <strong>{sharedDocs.length}</strong>
                </div>

                <div className={`grid-container ${viewMode}`}>
                    {filteredSharedDocs.length > 0 ? (
                        filteredSharedDocs.map(doc => renderDocumentCard(doc, { shared: true }))
                    ) : (
                        <div className="empty-state shared-empty">
                            <Share2 size={36} />
                            <h3>{searchQuery ? 'Không tìm thấy tài liệu được chia sẻ' : 'Chưa có tài liệu được chia sẻ'}</h3>
                            <p>
                                {searchQuery
                                    ? 'Thử đổi từ khóa hoặc kiểm tra lại bộ lọc.'
                                    : 'Khi người khác chia sẻ tài liệu qua email tài khoản, tài liệu sẽ hiển thị tại đây.'}
                            </p>
                        </div>
                    )}
                </div>
            </div>

            {isModalOpen && (
                <div className="modal" onClick={(e) => { if (e.target === e.currentTarget) closeUploadModal(); }}>
                    <div className="modal-content">
                        <button className="close-btn" onClick={closeUploadModal} type="button" disabled={isUploading}>
                            <X size={20} />
                        </button>

                        <div className="modal-title">
                            <div className="modal-icon">
                                <UploadCloud size={24} />
                            </div>

                            <div>
                                <h2>Tải lên tài liệu</h2>
                                <p>Hỗ trợ PDF, tối đa 50MB.</p>
                            </div>
                        </div>

                        <form onSubmit={handleUploadSubmit}>
                            <div className="drop-area" onClick={() => fileInputRef.current.click()}>
                                <FileUp size={38} />
                                <p>{selectedFile ? selectedFile.name : 'Chọn file PDF'}</p>
                                <span>Kéo thả hoặc bấm để chọn file</span>
                                <input
                                    type="file"
                                    ref={fileInputRef}
                                    accept=".pdf"
                                    style={{ display: 'none' }}
                                    onChange={handleFileChange}
                                    required
                                />
                            </div>

                            <div className="input-group">
                                <label>Tiêu đề</label>
                                <input
                                    type="text"
                                    value={uploadTitle}
                                    onChange={(e) => setUploadTitle(e.target.value)}
                                    required
                                />
                            </div>

                            <div className="input-group">
                                <label>Mô tả</label>
                                <textarea
                                    value={uploadDescription}
                                    onChange={(e) => setUploadDescription(e.target.value)}
                                    placeholder="Nhập mô tả ngắn cho tài liệu..."
                                    rows="3"
                                />
                            </div>

                            <div className="input-group">
                                <label>Nhãn dán</label>
                                <div className="tag-input-box">
                                    {uploadTags.map(tag => (
                                        <span key={tag} className="upload-tag">
                                            <Tag size={12} />
                                            {tag}
                                            <button type="button" onClick={() => removeTag(tag)}>
                                                <X size={12} />
                                            </button>
                                        </span>
                                    ))}

                                    <input
                                        type="text"
                                        value={tagInput}
                                        onChange={(e) => setTagInput(e.target.value)}
                                        onKeyDown={handleTagKeyDown}
                                        placeholder={uploadTags.length === 0 ? 'Nhập tag và nhấn Enter...' : ''}
                                    />
                                </div>
                                <span className="hint-text">Gợi ý: môn_học, AI, báo_cáo</span>
                            </div>

                            <div className="form-row">
                                <div className="input-group">
                                    <label>Danh mục</label>
                                    <select value={uploadCategory} onChange={(e) => setUploadCategory(e.target.value)}>
                                        <option value="khác">Khác</option>
                                        <option value="công_nghệ">Công nghệ</option>
                                        <option value="khoa_học">Khoa học</option>
                                    </select>
                                </div>

                                <div className="input-group">
                                    <label>Chế độ</label>
                                    <select value={uploadVisibility} onChange={(e) => setUploadVisibility(e.target.value)}>
                                        <option value="private">Private (Cá nhân)</option>
                                        <option value="public">Public (Cộng đồng)</option>
                                    </select>
                                </div>
                            </div>

                            {isUploading && (
                                <div className="upload-progress">
                                    <div style={{ width: `${uploadProgress}%` }} />
                                    <span>{uploadProgress < 100 ? `Đang tải lên ${uploadProgress}%` : 'Đang phân tích dữ liệu AI...'}</span>
                                </div>
                            )}

                            <button type="submit" className="btn-main upload-submit-btn" disabled={isUploading}>
                                {isUploading ? (
                                    <>
                                        <Bot size={17} />
                                        Đang xử lý...
                                    </>
                                ) : (
                                    <>
                                        <UploadCloud size={17} />
                                        Tải lên & lưu
                                    </>
                                )}
                            </button>
                        </form>
                    </div>
                </div>
            )}
        </>
    );
};

export default Dashboard;
