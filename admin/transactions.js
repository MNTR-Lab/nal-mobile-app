'use strict';
// Match the league's existing team-portal.html Transaction Center.
let txShowAll=false, operationsData=null, operationsView="transactions", rosterTeam="";
function txType(value){return String(value||'—').split('(')[0].trim();}
function txWaiting(value){const t=Date.parse(value);if(!Number.isFinite(t))return '—';const hours=Math.max(0,Math.floor((Date.now()-t)/3600000));return hours>=24?Math.floor(hours/24)+'d '+hours%24+'h':hours+'h';}
function txPill(state){return '<span class="status '+(state==='Approved'?'approved':state==='Needs Action'?'rejected':'pending')+'">'+esc(state)+'</span>';}
function txTable(rows,pending=false){
 if(!rows.length)return '<p class="empty">'+(pending?'No transactions are currently pending league review.':'No transactions match the selected filters.')+'</p>';
 return '<div class="table-wrap"><table><thead><tr><th>Player</th><th>Organization</th><th>Type</th><th>Position</th><th>Submitted</th>'+(pending?'<th>Waiting</th>':'')+'<th>Status</th><th></th></tr></thead><tbody>'+rows.map(t=>'<tr><td><strong>'+esc(t.player)+'</strong>'+(t.actionReason?'<br><small>'+esc(t.actionReason)+'</small>':'')+'</td><td>'+esc(t.organization||'—')+'</td><td>'+esc(txType(t.transactionType))+'</td><td>'+esc(t.position||'—')+'</td><td>'+esc(date(t.submittedAt))+'</td>'+(pending?'<td>'+esc(txWaiting(t.submittedAt))+'</td>':'')+'<td>'+txPill(t.state)+'</td><td>'+action('view-transaction','View','data-id="'+esc(t.id)+'"')+'</td></tr>').join('')+'</tbody></table></div>';
}
function initTransactions(data){
 operationsData=data;transactions=data.transactions?.all||[];txShowAll=false;
 if(operationsView==="rosters"){renderTeamRosters();return;}
 const organizations=[...new Set(transactions.map(t=>t.organization).filter(Boolean))].sort();
 const types=[...new Set(transactions.map(t=>txType(t.transactionType)))].sort();
 $('#page').innerHTML=operationsNavigation()+'<section class="tx-hero"><div><small class="tx-eyebrow">2027 SEASON</small><h2>Transaction Center</h2><p>League-wide transactions and live review status from the MNTR+ Database.</p></div><button type="button" class="tx-submit" data-action="transaction-new">+ SUBMIT NEW TRANSACTION</button></section>'+
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

function operationsNavigation(){return '<div class="actions" aria-label="League operations">'+action('operations-transactions','Transactions','',''+(operationsView==='transactions'?'primary':''))+action('operations-rosters','Team Rosters','',''+(operationsView==='rosters'?'primary':''))+'</div>';}
const rosterGroups=[['active','Active Roster'],['injuredReserve','Injured Reserve'],['commissionersExempt',"Commissioner's Exempt List"],['personalConductExempt','Personal Conduct Exempt List'],['suspended','Suspended Players'],['released','Released Players']];
function rosterSectionsFor(team){
 const sections=Object.fromEntries(rosterGroups.map(([key])=>[key,[]]));
 // The latest approved submission determines status. Editing an old record must not revive it.
 const latest=new Map();
 transactions.filter(t=>t.organization===team&&t.state==='Approved').forEach(t=>{
  const key=[t.firstName,t.lastName].map(v=>String(v||'').trim().toLowerCase()).join('|');if(key==='|')return;
  const old=latest.get(key),time=Date.parse(t.submittedAt||t.transactionDate)||0,oldTime=old?(Date.parse(old.submittedAt||old.transactionDate)||0):-1;
  if(!old||time>oldTime||(time===oldTime&&String(t.id).localeCompare(String(old.id),undefined,{numeric:true})>0))latest.set(key,t);
 });
 for(const t of latest.values()){
  const type=String(t.transactionType||'').toLowerCase().trim();
  const key=type==='release'?'released':type.includes('injury')?'injuredReserve':type.includes('commissioner')&&type.includes('exempt')?'commissionersExempt':type.includes('personal')&&type.includes('conduct')?'personalConductExempt':type.includes('suspension')?'suspended':t.activeRoster?'active':null;
  if(key)sections[key].push(t);
 }
 const order=['Quarterback','Running Back','Wide Receiver','Offensive Line','Defensive Line','Linebacker','Defensive Back','Kicker/Specialist','Athlete'];
 const rank=t=>{const i=order.indexOf(t.position);return i<0?999:i;};
 for(const players of Object.values(sections))players.sort((a,b)=>rank(a)-rank(b)||String(a.lastName||'').localeCompare(String(b.lastName||''))||String(a.firstName||'').localeCompare(String(b.firstName||'')));
 return sections;
}
function renderTeamRosters(){
 const teams=[...new Set([...(operationsData?.rosters?.organizations||[]),...transactions.map(t=>t.organization).filter(Boolean)])].sort();
 if(!teams.includes(rosterTeam))rosterTeam=teams[0]||'';
 $('#page').innerHTML=operationsNavigation()+'<section class="tx-hero"><div><small class="tx-eyebrow">2027 SEASON</small><h2>Team Rosters</h2><p>Current approved roster records and player transaction history.</p></div></section><section class="panel tx-filters"><label>Organization<select id="roster-team">'+teams.map(t=>'<option '+(t===rosterTeam?'selected':'')+'>'+esc(t)+'</option>').join('')+'</select></label><label>Player search<input id="roster-search" type="search" placeholder="Search roster players"></label></section><div id="roster-content"></div>';
 drawTeamRoster();
}
function drawTeamRoster(){
 const sections=rosterSectionsFor(rosterTeam),search=$('#roster-search').value.trim().toLowerCase();
 $('#roster-content').innerHTML='<h2>'+esc(rosterTeam||'No organizations available')+'</h2><section class="tx-summary">'+rosterGroups.map(([key,label])=>'<div class="tx-count"><small>'+esc(label)+'</small><strong>'+sections[key].length+'</strong></div>').join('')+'</section>'+rosterGroups.map(([key,label])=>{
 const rows=sections[key].filter(p=>String(p.player||[p.firstName,p.lastName].join(' ')).toLowerCase().includes(search));
 return '<section class="panel"><div class="panel-head"><h3>'+esc(label)+'</h3><span class="status">'+rows.length+' players</span></div>'+(rows.length?'<div class="table-wrap"><table><thead><tr><th>Player</th><th>Position</th><th>Height</th><th>Weight</th><th>College / school</th><th>Designation / reason</th><th>Actions</th></tr></thead><tbody>'+rows.map(p=>'<tr><td><strong>'+esc(p.player||[p.firstName,p.lastName].join(' '))+'</strong></td><td>'+esc(p.position||'—')+'</td><td>'+esc(p.height||'—')+'</td><td>'+esc(p.weight||'—')+'</td><td>'+esc(p.college||'—')+'</td><td>'+esc(p.injuryLength||p.suspensionReason||'—')+'</td><td>'+action('player-history','History','data-id="'+esc(p.id)+'"')+(current.user.role==='super_admin'?action('roster-manage','Manage player','data-id="'+esc(p.id)+'" data-status="'+esc(key)+'"'):'')+'</td></tr>').join('')+'</tbody></table></div>':'<p class="empty">'+(search?'No matching players.':'No players are currently listed in this section.')+'</p>')+'</section>';
 }).join('');
}
function playerHistory(id){
 const player=transactions.find(t=>String(t.id)===String(id));if(!player)return;
 const key=t=>[t.firstName,t.lastName].map(v=>String(v||'').trim().toLowerCase()).join('|');
 const history=transactions.filter(t=>key(t)===key(player)).sort((a,b)=>(Date.parse(b.submittedAt||b.transactionDate)||0)-(Date.parse(a.submittedAt||a.transactionDate)||0));
 showEditor('Player history — '+player.player,txTable(history));
}
document.addEventListener('click',e=>{
 const b=e.target.closest('button[data-action]');if(!b)return;
 if(b.dataset.action==='operations-rosters'){operationsView='rosters';renderTeamRosters();}
 if(b.dataset.action==='operations-transactions'){operationsView='transactions';initTransactions(operationsData);}
 if(b.dataset.action==='player-history')playerHistory(b.dataset.id);
 if(b.dataset.action==='roster-manage')rosterEditor(b.dataset.id,b.dataset.status);
});
document.addEventListener('change',e=>{if(e.target.id==='roster-team'){rosterTeam=e.target.value;drawTeamRoster();}});
document.addEventListener('input',e=>{if(e.target.id==='roster-search')drawTeamRoster();});
