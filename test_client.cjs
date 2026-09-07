// Optional Node checks against JavaScript extracted from the actual one-file app.
const {execFileSync}=require('node:child_process');
const vm=require('node:vm'),assert=require('node:assert/strict');
const source=execFileSync(process.env.PYTHON || 'python',['-c',"import pokemon_team; print(pokemon_team.ASSETS['app.js'])"],{cwd:__dirname,encoding:'utf8'}).split('\nif (isSettings) {')[0];
const available=new Set(),requests=[];
class MockImage {set src(url){requests.push(url);queueMicrotask(()=>available.has(url)?this.onload?.():this.onerror?.());}}
const context={document:{body:{dataset:{page:'overlay'}}},Image:MockImage,setTimeout,clearTimeout};
vm.createContext(context);
vm.runInContext(source+'\nthis.api={portraitURL,candidates,resolvePortrait,dimensions};this.setState=x=>state=x;',context);
const {portraitURL,candidates,resolvePortrait,dimensions}=context.api;
(async()=>{
  assert.equal(portraitURL(1,'',true),'https://raw.githubusercontent.com/PMDCollab/SpriteCollab/master/portrait/0001/0000/0001/Normal.png');
  assert.equal(portraitURL(52,1,true),'https://raw.githubusercontent.com/PMDCollab/SpriteCollab/master/portrait/0052/0001/0001/Normal.png');
  available.add(portraitURL(1,0));assert.equal(await resolvePortrait(1,''),portraitURL(1,0));
  available.add(portraitURL(52));requests.length=0;
  await assert.rejects(resolvePortrait(52,1,true));assert.equal(requests.length,1);
  context.setState({slots:Array(6).fill(null),layout:'vertical'});
  assert.equal(dimensions().height,528);assert.equal(dimensions().width,88);
  context.setState({slots:[{dex:1},null,null,null,null,null],layout:'grid',style:{size:96,gap:12,labels:true,hideEmpty:true}});
  assert.equal(dimensions().width,104);assert.equal(dimensions().height,130);
  context.setState({slots:[{dex:1},null,null,null,null,null],layout:'grid',style:{size:96,gap:12,labels:true,hideEmpty:true},challenge:{enabled:true},hunt:{enabled:true,target:{dex:1}}});
  assert.equal(dimensions().width,188);assert.equal(dimensions().height,262);
  console.log('PASS: shiny URLs, unavailable portraits, fallback, customized overlay dimensions');
})().catch(e=>{console.error(e);process.exitCode=1;});
