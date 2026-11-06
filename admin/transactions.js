'use strict';
// Match the league's existing team-portal.html Transaction Center.
let txShowAll=false;
function txType(value){return String(value||'—').split('(')[0].trim();}
function txWaiting(value){const t=Date.parse(value);if(!Number.isFinite(t))return '—';const hours=Math.max(0,Math.floor((Date.now()-t)/3600000));return hours>=24?Math.floor(hours/24)+'d '+hours%24+'h':hours+'h';}
function txPill(state){return '<span class="status '+(state==='Approved'?'approved':state==='Needs Action'?'rejected':'pending')+'">'+esc(state)+'</span>';}
function txTable(rows,pending=false){
 if(!rows.length)return '<p class="empty">'+(pending?'No transactions are currently pending league review.':'No transactions match the selected filters.')+'</p>';
 return '<div class="table-wrap"><table><thead><tr><th>Player</th><th>Organization</th><th>Type</th><th>Position</th><th>Submitted</th>'+(pending?'<th>Waiting</th>':'')+'<th>Status</th><th></th></tr></thead><tbody>'+rows.map(t=>'<tr><td><strong>'+esc(t.player)+'</strong>'+(t.actionReason?'<br><small>'+esc(t.actionReason)+'</small>':'')+'</td><td>'+esc(t.organization||'—')+'</td><td>'+esc(txType(t.transactionType))+'</td><td>'+esc(t.position||'—')+'</td><td>'+esc(date(t.submittedAt))+'</td>'+(pending?'<td>'+esc(txWaiting(t.submittedAt))+'</td>':'')+'<td>'+txPill(t.state)+'</td><td>'+action('view-transaction','View','data-id="'+esc(t.id)+'"')+'</td></tr>').join('')+'</tbody></table></div>';
}
function initTransactions(data){
 transactions=data.transactions?.all||[];txShowAll=false;
 const organizations=[...new Set(transactions.map(t=>t.organization).filter(Boolean))].sort();
 const types=[...new Set(transactions.map(t=>txType(t.transactionType)))].sort();
 $('#page').innerHTML='<section class="tx-hero"><div><small class="tx-eyebrow">2027 SEASON</small><h2>Transaction Center</h2><p>League-wide transactions and live review status from the MNTR+ Database.</p></div><button type="button" class="tx-submit" data-action="transaction-new">+ SUBMIT NEW TRANSACTION</button></section>'+
 '<section class="panel tx-filters"><label>Organization<select id="tx-org"><option value="">All Organizations</option>'+organizations.map(v=>'<option>'+esc(v)+'</option>').join('')+'</select></label><label>Transaction type<select id="tx-type"><option value="">All Transaction Types</option>'+types.map(v=>'<option>'+esc(v)+'</option>').join('')+'</select></label><label>Status<select id="tx-status"><option value="">All Statuses</option><option>Pending</option><option>Approved</option><option>Needs Action</option></select></label><label>Player search<input id="tx-search" type="search" placeholder="Search player name…"></label></section>'+
 '<section class="tx-summary">'+[['Pending','PENDING LEAGUE REVIEW','Awaiting league decision'],['Approved','APPROVED','Approved 2027 transactions'],['Needs Action','NEEDS ACTION','Returned or rejected submissions']].map(([state,label,description])=>'<button type="button" data-action="tx-filter" data-status="'+state+'" class="tx-count"><small>'+label+'</small><strong>'+transactions.filter(t=>t.state===state).length+'</strong><span>'+description+'</span></button>').join('')+'</section>'+
 '<section class="panel"><div class="panel-head"><h3>Pending Transactions</h3><span class="status pending">'+transactions.filter(t=>t.state==='Pending').length+' pending</span></div><div class="tx-notice"><strong>Live league review queue</strong><br>Submissions appear here while they remain pending in the MNTR+ Database.</div><div id="tx-pending"></div></section>'+
 '<section class="panel" id="tx-recent-panel"><div class="panel-head"><h3 id="tx-heading">Recent Transactions</h3><span id="tx-record-count" class="status"></span></div><div id="tx-list"></div><div class="actions tx-footer">'+action('tx-all','See all transactions','','primary')+action('tx-recent','← Back to recent transactions')+'</div></section>';
 drawTransactions();
}
function drawTransactions(){
 const search=$('#tx-search').value.trim().toLowerCase(),status=$('#tx-status').value,org=$('#tx-org').value,type=$('#tx-type').value;
 const matching=transactions.filter(t=>(!status||t.state===status)&&(!org||t.organization===org)&&(!type||txType(t.transactionType)===type)&&String(t.player||'').toLowerCase().includes(search)).sort((a,b)=>(Date.parse(b.submittedAt||b.transactionDate)||0)-(Date.parse(a.submittedAt||a.transactionDate)||0));
 $('#tx-pending').innerHTML=txTable(transactions.filter(t=>t.state==='Pending'),true);
 const shown=txShowAll?matching:matching.slice(0,10);
 $('#tx-list').innerHTML=txTable(shown);
 $('#tx-heading').textContent=txShowAll?'All Transactions':'Recent Transactions';
 $('#tx-record-count').textContent=txShowAll?matching.length+' records':shown.length+' of '+matching.length;
 document.querySelector('[data-action="tx-all"]').hidden=txShowAll||matching.length<=10;
 document.querySelector('[data-action="tx-recent"]').hidden=!txShowAll;
}
function transactionDetail(id){
 const t=transactions.find(t=>String(t.id)===String(id));if(!t)return;
 const fields=[['Organization',t.organization],['Transaction type',t.transactionType],['Position',t.position],['Submitted',date(t.submittedAt)],['Transaction date',t.transactionDate],['Height',t.height],['Weight',t.weight],['College / school',t.college],['Professional experience',t.professionalExperience]];
 const details=[['Needs action',t.actionReason],['Trade details',t.tradeDetails],['Injury designation',t.injuryLength],['Suspension reason',t.suspensionReason]].filter(([,v])=>v);
 showEditor(t.player||'Transaction details',txPill(t.state)+'<div class="tx-detail-grid">'+fields.map(([label,v])=>'<div><small>'+label+'</small><strong>'+esc(v||'—')+'</strong></div>').join('')+'</div>'+details.map(([label,v])=>'<div class="tx-notice"><strong>'+label+'</strong><p>'+esc(v)+'</p></div>').join('')+'<div class="tx-timeline"><strong>Submitted</strong><p>'+esc(date(t.submittedAt))+'</p><strong>Current review status: '+esc(t.state)+'</strong><p>Last updated '+esc(date(t.updatedAt))+'</p></div><div class="actions">'+action('transaction-edit','Edit / review transaction','data-id="'+esc(t.id)+'"')+''+(current.user.role==='super_admin'?action('roster-from-detail','Update player roster','data-id="'+esc(t.id)+'"'):'')+'</div>');
}
