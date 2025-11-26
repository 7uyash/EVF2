import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function App() {
  const [activeTab, setActiveTab] = useState('finder');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [error, setError] = useState(null);

  // Email Finder state
  const [finderForm, setFinderForm] = useState({
    first_name: '',
    last_name: '',
    domain: '',
    max_results: 2,
    include_default_patterns: true,
    fast_mode: true,
    confidence_mode: 'balanced',
  });
  const [customPatternText, setCustomPatternText] = useState('');

  // Email Verifier state
  const [verifierForm, setVerifierForm] = useState({
    email: '',
    fast_mode: true,
    confidence_mode: 'balanced',
  });

  // CSV upload state
  const [csvFile, setCsvFile] = useState(null);
  const [csvType, setCsvType] = useState('find'); // 'find' or 'verify'
  const [bulkOptions, setBulkOptions] = useState({ fast_mode: true, confidence_mode: 'balanced' });
  const [bulkJob, setBulkJob] = useState(null);
  const [jobPollId, setJobPollId] = useState(null);
  const bulkProcessingActive = bulkJob && ['pending', 'running'].includes(bulkJob.status);

  useEffect(() => {
    return () => {
      if (jobPollId) {
        clearInterval(jobPollId);
      }
    };
  }, [jobPollId]);

  const startJobPolling = (jobId) => {
    if (jobPollId) {
      clearInterval(jobPollId);
    }
    const intervalId = setInterval(async () => {
      try {
        const { data } = await axios.get(`${API_BASE}/api/jobs/${jobId}`);
        setBulkJob(data);
        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(intervalId);
          setJobPollId(null);
          if (data.status === 'failed') {
            setError(data.message || 'Bulk job failed. Please try again.');
          }
        }
      } catch (err) {
        clearInterval(intervalId);
        setJobPollId(null);
        setError(err.response?.data?.detail || err.message || 'Failed to fetch job status');
      }
    }, 1200);
    setJobPollId(intervalId);
  };

  const handleDownloadResults = async () => {
    if (!bulkJob?.id) {
      setError('No completed job to download.');
      return;
    }
    if (!bulkJob.download_ready) {
      setError('Results are not ready for download yet.');
      return;
    }

    try {
      const response = await axios.get(`${API_BASE}/api/jobs/${bulkJob.id}/download`, {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      const headerNameRaw = response.headers['content-disposition']?.split('filename=')[1];
      const headerName = headerNameRaw ? headerNameRaw.replace(/"/g, '') : null;
      link.href = url;
      link.setAttribute('download', headerName || 'bulk_results.csv');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to download results');
    }
  };

  const handleFindEmail = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResults([]);

    try {
      const customPatterns = customPatternText
        .split(/\r?\n/)
        .map((pattern) => pattern.trim())
        .filter((pattern) => pattern.length > 0);

      const payload = {
        first_name: finderForm.first_name,
        last_name: finderForm.last_name,
        domain: finderForm.domain,
        max_results: Number(finderForm.max_results) || 2,
        include_default_patterns: finderForm.include_default_patterns,
        fast_mode: finderForm.fast_mode,
        confidence_mode: finderForm.confidence_mode,
      };

      if (customPatterns.length > 0) {
        payload.custom_patterns = customPatterns;
      }

      const response = await axios.post(`${API_BASE}/api/find`, payload, {
        timeout: 30000 // 30 second timeout
      });
      setResults(response.data);
    } catch (err) {
      if (err.code === 'ECONNABORTED') {
        setError('Request timed out. Please check if the backend server is running.');
      } else if (err.code === 'ERR_NETWORK' || err.message.includes('Network Error')) {
        setError('Cannot connect to backend server. Make sure it\'s running on http://localhost:8000');
      } else {
        setError(err.response?.data?.detail || err.message || 'An error occurred');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyEmail = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResults([]);

    try {
      const payload = {
        email: verifierForm.email,
        fast_mode: verifierForm.fast_mode,
        confidence_mode: verifierForm.confidence_mode,
      };

      const response = await axios.post(`${API_BASE}/api/verify`, payload, {
        timeout: 30000 // 30 second timeout
      });
      setResults([response.data]);
    } catch (err) {
      if (err.code === 'ECONNABORTED') {
        setError('Request timed out. Please check if the backend server is running.');
      } else if (err.code === 'ERR_NETWORK' || err.message.includes('Network Error')) {
        setError('Cannot connect to backend server. Make sure it\'s running on http://localhost:8000');
      } else {
        setError(err.response?.data?.detail || err.message || 'An error occurred');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCsvUpload = async (e) => {
    e.preventDefault();
    if (!csvFile) {
      setError('Please select a CSV file');
      return;
    }

    setLoading(true);
    setError(null);
    setResults([]);

    try {
      const formData = new FormData();
      formData.append('file', csvFile);
      formData.append('fast_mode', bulkOptions.fast_mode ? 'true' : 'false');
      formData.append('confidence_mode', bulkOptions.confidence_mode || 'balanced');

      const isFindJob = csvType === 'find';
      const endpoint = isFindJob 
        ? `${API_BASE}/api/bulk-find`
        : `${API_BASE}/api/bulk-verify`;

      const response = await axios.post(endpoint, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      const { job_id: jobId, total_rows: totalRows } = response.data || {};
      if (!jobId) {
        throw new Error('Job ID missing from server response');
      }

      const placeholder = {
        id: jobId,
        type: isFindJob ? 'bulk_find' : 'bulk_verify',
        status: 'pending',
        progress: totalRows ? 0 : 100,
        total_rows: totalRows ?? 0,
        processed_rows: 0,
        success_rows: 0,
        error_rows: 0,
        download_ready: false,
        recent_errors: [],
      };

      setBulkJob(placeholder);
      startJobPolling(jobId);
      setCsvFile(null);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setResults([]);
    setError(null);
  };

  const getStatusBadge = (status) => {
    const badges = {
      'valid': 'success',
      'invalid': 'danger',
      'catch-all': 'warning',
      'unknown': 'secondary',
      'not_found': 'info',
      'error': 'danger'
    };
    return badges[status] || 'secondary';
  };

  return (
    <div className="App">
      <div className="container mt-4">
        <div className="text-center mb-4">
          <h1 className="display-4">📧 Email Finder & Verifier</h1>
          <p className="lead">Find and verify email addresses with confidence</p>
        </div>

        {/* Tabs */}
        <ul className="nav nav-tabs mb-4" role="tablist">
          <li className="nav-item">
            <button
              className={`nav-link ${activeTab === 'finder' ? 'active' : ''}`}
              onClick={() => handleTabChange('finder')}
            >
              Email Finder
            </button>
          </li>
          <li className="nav-item">
            <button
              className={`nav-link ${activeTab === 'verifier' ? 'active' : ''}`}
              onClick={() => handleTabChange('verifier')}
            >
              Email Verifier
            </button>
          </li>
          <li className="nav-item">
            <button
              className={`nav-link ${activeTab === 'bulk' ? 'active' : ''}`}
              onClick={() => handleTabChange('bulk')}
            >
              Bulk Processing
            </button>
          </li>
        </ul>

        {/* Email Finder Tab */}
        {activeTab === 'finder' && (
          <div className="card">
            <div className="card-body">
              <h3 className="card-title mb-4">Find Email Address</h3>
              <form onSubmit={handleFindEmail}>
                <div className="row mb-3">
                  <div className="col-md-4">
                    <label htmlFor="first_name" className="form-label">First Name</label>
                    <input
                      type="text"
                      className="form-control"
                      id="first_name"
                      value={finderForm.first_name}
                      onChange={(e) => setFinderForm({...finderForm, first_name: e.target.value})}
                      required
                    />
                  </div>
                  <div className="col-md-4">
                    <label htmlFor="last_name" className="form-label">Last Name</label>
                    <input
                      type="text"
                      className="form-control"
                      id="last_name"
                      value={finderForm.last_name}
                      onChange={(e) => setFinderForm({...finderForm, last_name: e.target.value})}
                      required
                    />
                  </div>
                  <div className="col-md-4">
                    <label htmlFor="domain" className="form-label">Company Domain</label>
                    <input
                      type="text"
                      className="form-control"
                      id="domain"
                      value={finderForm.domain}
                      onChange={(e) => setFinderForm({...finderForm, domain: e.target.value})}
                      placeholder="example.com"
                      required
                    />
                  </div>
                  <div className="col-md-4">
                    <label htmlFor="max_results" className="form-label">Suggestions</label>
                    <select
                      className="form-select"
                      id="max_results"
                      value={finderForm.max_results}
                      onChange={(e) => setFinderForm({...finderForm, max_results: e.target.value})}
                    >
                      <option value={2}>Top 2</option>
                      <option value={5}>Top 5</option>
                      <option value={10}>Top 10</option>
                      <option value={15}>Top 15</option>
                    </select>
                    <div className="form-text">
                      Higher numbers may take a little longer to verify.
                    </div>
                  </div>
                </div>
                <div className="row mb-3">
                  <div className="col-md-8">
                    <label htmlFor="custom_patterns" className="form-label">Custom Patterns (optional)</label>
                    <textarea
                      className="form-control"
                      id="custom_patterns"
                      rows={4}
                      value={customPatternText}
                      onChange={(e) => setCustomPatternText(e.target.value)}
                      placeholder="{first}.{last}\n{f}{last}"
                    />
                    <div className="form-text">
                      One pattern per line. Available tokens: &#123;first&#125;, &#123;last&#125;, &#123;f&#125;, &#123;l&#125;, &#123;domain&#125;.
                    </div>
                  </div>
                  <div className="col-md-4">
                    <div className="form-check form-switch mt-2">
                      <input
                        className="form-check-input"
                        type="checkbox"
                        id="include_defaults"
                        checked={finderForm.include_default_patterns}
                        onChange={(e) => setFinderForm({...finderForm, include_default_patterns: e.target.checked})}
                      />
                      <label className="form-check-label" htmlFor="include_defaults">
                        Include default patterns
                      </label>
                    </div>
                    <div className="form-check form-switch mt-3">
                      <input
                        className="form-check-input"
                        type="checkbox"
                        id="finder_fast_mode"
                        checked={finderForm.fast_mode}
                        onChange={(e) => setFinderForm({...finderForm, fast_mode: e.target.checked})}
                      />
                      <label className="form-check-label" htmlFor="finder_fast_mode">
                        Fast verification mode
                      </label>
                    </div>
                    <div className="form-text">
                      Disable fast mode to run exhaustive SMTP + catch-all checks (slower but more precise).
                    </div>
                    <div className="mt-3">
                      <label htmlFor="finder_confidence_mode" className="form-label">Confidence Mode</label>
                      <select
                        className="form-select"
                        id="finder_confidence_mode"
                        value={finderForm.confidence_mode}
                        onChange={(e) => setFinderForm({...finderForm, confidence_mode: e.target.value})}
                      >
                        <option value="balanced">Balanced</option>
                        <option value="aggressive">Aggressive (higher scores)</option>
                      </select>
                      <div className="form-text">
                        Aggressive mode boosts confidence when SMTP servers stay silent.
                      </div>
                    </div>
                  </div>
                </div>
                <button type="submit" className="btn btn-primary" disabled={loading}>
                  {loading ? (
                    <>
                      <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                      Finding...
                    </>
                  ) : (
                    'Find Email'
                  )}
                </button>
              </form>
            </div>
          </div>
        )}

        {/* Email Verifier Tab */}
        {activeTab === 'verifier' && (
          <div className="card">
            <div className="card-body">
              <h3 className="card-title mb-4">Verify Email Address</h3>
              <form onSubmit={handleVerifyEmail}>
                <div className="row mb-3">
                  <div className="col-md-8">
                    <label htmlFor="email" className="form-label">Email Address</label>
                    <input
                      type="email"
                      className="form-control"
                      id="email"
                      value={verifierForm.email}
                      onChange={(e) => setVerifierForm({...verifierForm, email: e.target.value})}
                      placeholder="john.doe@example.com"
                      required
                    />
                  </div>
                </div>
                <div className="form-check form-switch mb-3">
                  <input
                    className="form-check-input"
                    type="checkbox"
                    id="verifier_fast_mode"
                    checked={verifierForm.fast_mode}
                    onChange={(e) => setVerifierForm({...verifierForm, fast_mode: e.target.checked})}
                  />
                  <label className="form-check-label" htmlFor="verifier_fast_mode">
                    Fast verification mode
                  </label>
                  <div className="form-text">
                    Disable to perform full SMTP + catch-all checks (may take longer).
                  </div>
                </div>
                <div className="mb-3">
                  <label htmlFor="verifier_confidence_mode" className="form-label">Confidence Mode</label>
                  <select
                    className="form-select"
                    id="verifier_confidence_mode"
                    value={verifierForm.confidence_mode}
                    onChange={(e) => setVerifierForm({...verifierForm, confidence_mode: e.target.value})}
                  >
                    <option value="balanced">Balanced</option>
                    <option value="aggressive">Aggressive (higher scores)</option>
                  </select>
                  <div className="form-text">
                    Aggressive mode raises confidence when only DNS/security checks succeed.
                  </div>
                </div>
                <button type="submit" className="btn btn-primary" disabled={loading}>
                  {loading ? (
                    <>
                      <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                      Verifying...
                    </>
                  ) : (
                    'Verify Email'
                  )}
                </button>
              </form>
            </div>
          </div>
        )}

        {/* Bulk Processing Tab */}
        {activeTab === 'bulk' && (
          <div className="card">
            <div className="card-body">
              <h3 className="card-title mb-4">Bulk Processing</h3>
              <form onSubmit={handleCsvUpload}>
                <div className="mb-3">
                  <label htmlFor="csv_type" className="form-label">Processing Type</label>
                  <select
                    className="form-select"
                    id="csv_type"
                    value={csvType}
                    onChange={(e) => setCsvType(e.target.value)}
                  >
                    <option value="find">Find Emails (requires: first_name, last_name, domain)</option>
                    <option value="verify">Verify Emails (requires: email)</option>
                  </select>
                </div>
                <div className="mb-3">
                  <label htmlFor="csv_file" className="form-label">CSV File</label>
                  <input
                    type="file"
                    className="form-control"
                    id="csv_file"
                    accept=".csv"
                    onChange={(e) => setCsvFile(e.target.files[0])}
                    required
                  />
                  <div className="form-text">
                    {csvType === 'find' 
                      ? 'CSV must have columns: first_name, last_name, domain'
                      : 'CSV must have column: email'}
                  </div>
                </div>
                <div className="form-check form-switch mb-3">
                  <input
                    className="form-check-input"
                    type="checkbox"
                    id="bulk_fast_mode"
                    checked={bulkOptions.fast_mode}
                    onChange={(e) => setBulkOptions({...bulkOptions, fast_mode: e.target.checked})}
                  />
                  <label className="form-check-label" htmlFor="bulk_fast_mode">
                    Fast verification mode
                  </label>
                  <div className="form-text">
                    Disable to run deep SMTP + catch-all checks for each row (slower).
                  </div>
                </div>
                <div className="mb-3">
                  <label htmlFor="bulk_confidence_mode" className="form-label">Confidence Mode</label>
                  <select
                    className="form-select"
                    id="bulk_confidence_mode"
                    value={bulkOptions.confidence_mode}
                    onChange={(e) => setBulkOptions({...bulkOptions, confidence_mode: e.target.value})}
                  >
                    <option value="balanced">Balanced</option>
                    <option value="aggressive">Aggressive (higher scores)</option>
                  </select>
                  <div className="form-text">
                    Aggressive mode boosts confidence on hard-to-verify domains.
                  </div>
                </div>
                <button type="submit" className="btn btn-primary" disabled={loading || bulkProcessingActive}>
                  {loading ? (
                    <>
                      <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                      Processing...
                    </>
                  ) : (
                    'Upload & Process'
                  )}
                </button>
              </form>
            </div>
          </div>
        )}
        {bulkJob && (
          <div className="card mt-4">
            <div className="card-body">
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div>
                  <strong>Bulk Job Status:</strong> {bulkJob.status}
                </div>
                <div>
                  <strong>Progress:</strong> {(bulkJob.progress || 0).toFixed(1)}%
                </div>
              </div>
              <div className="progress mb-3" style={{height: '1.25rem'}}>
                <div
                  className="progress-bar"
                  role="progressbar"
                  style={{width: `${bulkJob.progress || 0}%`}}
                  aria-valuenow={bulkJob.progress || 0}
                  aria-valuemin="0"
                  aria-valuemax="100"
                >
                  {Math.round(bulkJob.progress || 0)}%
                </div>
              </div>
              <div className="row text-center">
                <div className="col-md-3 mb-2">
                  <small>Total</small>
                  <div className="fw-bold">{bulkJob.total_rows ?? '—'}</div>
                </div>
                <div className="col-md-3 mb-2">
                  <small>Processed</small>
                  <div className="fw-bold">{bulkJob.processed_rows ?? 0}</div>
                </div>
                <div className="col-md-3 mb-2">
                  <small>Success</small>
                  <div className="fw-bold text-success">{bulkJob.success_rows ?? 0}</div>
                </div>
                <div className="col-md-3 mb-2">
                  <small>Errors</small>
                  <div className="fw-bold text-danger">{bulkJob.error_rows ?? 0}</div>
                </div>
              </div>
              {bulkJob.message && (
                <div className="alert alert-info mt-3 mb-0" role="alert">
                  {bulkJob.message}
                </div>
              )}
              {bulkJob.recent_errors && bulkJob.recent_errors.length > 0 && (
                <div className="mt-3">
                  <strong>Recent errors:</strong>
                  <ul className="mb-0">
                    {bulkJob.recent_errors.map((errMsg, idx) => (
                      <li key={`${errMsg}-${idx}`}>{errMsg}</li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="mt-3 d-flex gap-2">
                <button
                  type="button"
                  className="btn btn-success"
                  onClick={handleDownloadResults}
                  disabled={!bulkJob.download_ready}
                >
                  Download Results
                </button>
                <button
                  type="button"
                  className="btn btn-outline-secondary"
                  onClick={() => setBulkJob(null)}
                  disabled={bulkProcessingActive}
                >
                  Clear Progress
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="alert alert-danger mt-3" role="alert">
            <strong>Error:</strong> {error}
          </div>
        )}

        {/* Results Display */}
        {results.length > 0 && (
          <div className="card mt-4">
            <div className="card-body">
              <h4 className="card-title mb-3">Results</h4>
              <div className="table-responsive">
                <table className="table table-striped">
                  <thead>
                    <tr>
                      <th>Email</th>
                      <th>Status</th>
                      <th>Reason</th>
                      {activeTab === 'verifier' && (
                        <>
                          <th>DNS / MX Check</th>
                          <th>SMTP Handshake Test</th>
                          <th>Details</th>
                        </>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((result, index) => (
                      <tr key={index}>
                        <td>{result.email || 'N/A'}</td>
                        <td>
                          <span className={`badge bg-${getStatusBadge(result.status)}`}>
                            {result.status}
                          </span>
                        </td>
                        <td>{result.reason || 'N/A'}</td>
                        {activeTab === 'verifier' && (
                          <>
                            <td>
                              {result.details?.mx_check?.valid ? (
                                <ul className="mb-0 ps-3">
                                  <li>Domain exists</li>
                                  <li>MX records active</li>
                                </ul>
                              ) : (
                                <span>MX/DNS issue</span>
                              )}
                            </td>
                            <td>
                              {result.details?.smtp_check?.skipped && (
                                <span>Skipped (provider blocks check)</span>
                              )}
                              {!result.details?.smtp_check?.skipped && result.details?.smtp_check?.accepted && (
                                <span>Server responds, mailbox accepts</span>
                              )}
                              {!result.details?.smtp_check?.skipped && result.details?.smtp_check?.rejected && (
                                <span>Mailbox rejects RCPT TO</span>
                              )}
                              {!result.details?.smtp_check?.skipped &&
                                !result.details?.smtp_check?.accepted &&
                                !result.details?.smtp_check?.rejected && (
                                  <span>No clear response (timeout or greylist)</span>
                                )}
                            </td>
                            <td>
                              {result.details ? (
                                <details>
                                  <summary>View Raw Details</summary>
                                  <pre className="mt-2 p-2 bg-light" style={{fontSize: '0.85rem'}}>
                                    {JSON.stringify(result.details, null, 2)}
                                  </pre>
                                </details>
                              ) : (
                                'N/A'
                              )}
                            </td>
                          </>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;

