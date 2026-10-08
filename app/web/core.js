/* Pure reading logic shared by the application and its tests. */
(function(root){
  function words(text){return Array.from(text.matchAll(/\S+/gu),m=>({text:m[0],offset:m.index,end:m.index+m[0].length}));}
  function chunk(text,tokens,start){
    if(start<0||start>=tokens.length)return null;
    let end=start;
    while(end<tokens.length){
      const length=tokens[end].end-tokens[start].offset;
      if(length>260&&end>start)break;
      end++;
      if(length>=100&&/[.!?…][”"')\]]?$/u.test(tokens[end-1].text))break;
    }
    return {start,end,text:text.slice(tokens[start].offset,tokens[end-1].end)};
  }
  function boundaryAt(timings,time){
    let low=0,high=timings.length-1,answer=-1;
    while(low<=high){const mid=(low+high)>>1;if(timings[mid].start<=time){answer=mid;low=mid+1;}else high=mid-1;}
    return answer<0?null:timings[answer];
  }
  const api={words,chunk,boundaryAt};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  root.BABCore=api;
})(typeof globalThis!=='undefined'?globalThis:this);
